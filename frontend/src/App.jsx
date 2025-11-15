import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [questions, setQuestions] = useState([]);
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(true);
  const [fetchError, setFetchError] = useState("");

  const [authMode, setAuthMode] = useState("signup"); // signup | login
  const [signupForm, setSignupForm] = useState({
    name: "",
    password: "",
    age: "",
    country: "",
    deliveredAt: "",
  });
  const [loginForm, setLoginForm] = useState({ name: "", password: "" });
  const [motherId, setMotherId] = useState(null);
  const [step, setStep] = useState("auth"); // auth | questions | done
  const [resumeQuestionId, setResumeQuestionId] = useState(null);

  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState("");
  const [textAnswer, setTextAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const answeredCacheRef = useRef(new Map());
  const prefillingRef = useRef(false);
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    const loadQuestions = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/questions`);
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail || "Unable to load questions");
        }
        setQuestions(data);
      } catch (err) {
        console.error(err);
        setFetchError(err.message || "Failed to load questions");
      } finally {
        setIsLoadingQuestions(false);
      }
    };

    loadQuestions();
  }, []);

  useEffect(() => {
    if (!questions.length) return;

    if (resumeQuestionId) {
      const idx = questions.findIndex((q) => q.id === resumeQuestionId);
      if (idx >= 0) {
        setCurrentIndex(idx);
      } else {
        setCurrentIndex(0);
      }
    } else {
      setCurrentIndex(0);
    }
  }, [resumeQuestionId, questions]);

  const currentQuestion = questions[currentIndex];
  const hasOptions = currentQuestion?.options?.length > 0;

  const signupValid = useMemo(() => {
    return (
      signupForm.name.trim() &&
      signupForm.password.trim() &&
      signupForm.age.trim() &&
      signupForm.country.trim() &&
      signupForm.deliveredAt
    );
  }, [signupForm]);

  const loginValid = useMemo(() => {
    return loginForm.name.trim() && loginForm.password.trim();
  }, [loginForm]);

  const handleSignupChange = (field, value) => {
    setSignupForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleLoginChange = (field, value) => {
    setLoginForm((prev) => ({ ...prev, [field]: value }));
  };

  const loadCachedAnswer = (question) => {
    prefillingRef.current = true;
    const cachedValue = question
      ? answeredCacheRef.current.get(question.id)
      : null;

    if (!question || !cachedValue) {
      setSelectedOption("");
      setTextAnswer("");
    } else if (question.options?.some((opt) => opt.value === cachedValue)) {
      setSelectedOption(cachedValue);
      setTextAnswer("");
    } else {
      setTextAnswer(cachedValue);
      setSelectedOption("");
    }
    prefillingRef.current = false;
    setIsDirty(false);
  };

  useEffect(() => {
    if (!currentQuestion) {
      setSelectedOption("");
      setTextAnswer("");
      setIsDirty(false);
      return;
    }
    loadCachedAnswer(currentQuestion);
  }, [currentQuestion ? currentQuestion.id : null]);

  const handleOptionSelect = (value) => {
    setSelectedOption(value);
    setTextAnswer("");
    if (!prefillingRef.current) setIsDirty(true);
  };

  const handleTextChange = (value) => {
    setTextAnswer(value);
    setSelectedOption("");
    if (!prefillingRef.current) setIsDirty(true);
  };

  const handlePrev = () => {
    if (currentIndex === 0) return;
    setCurrentIndex((prev) => Math.max(prev - 1, 0));
    setIsDirty(false);
  };

  const handleSignupSubmit = async (event) => {
    event.preventDefault();
    if (!signupValid) return;

    setIsSubmitting(true);
    try {
      const payload = {
        name: signupForm.name.trim(),
        password: signupForm.password,
        age: signupForm.age ? Number(signupForm.age) : null,
        country: signupForm.country.trim(),
        delivered_at: signupForm.deliveredAt
          ? new Date(signupForm.deliveredAt).toISOString()
          : null,
      };

      const res = await fetch(`${API_BASE}/api/mothers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Unable to create your Majka profile");
      }

      setMotherId(data.mother_id);
      setResumeQuestionId(null);
      answeredCacheRef.current = new Map();
      setSelectedOption("");
      setTextAnswer("");
      setIsDirty(false);
      setStep("questions");
    } catch (err) {
      console.error(err);
      alert(err.message || "Unable to start intake");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLoginSubmit = async (event) => {
    event.preventDefault();
    if (!loginValid) return;

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: loginForm.name.trim(),
          password: loginForm.password,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Invalid name or password");
      }

      setMotherId(data.mother_id);
      const answeredEntries = Object.entries(data.answered_answers || {}).map(
        ([key, value]) => [Number(key), value]
      );
      answeredCacheRef.current = new Map(answeredEntries);

      const resumeId = data.resume_question_id ?? null;
      setResumeQuestionId(resumeId);
      setIsDirty(false);

      const totalQuestions = questions.length;
      const answeredCount = answeredEntries.length;

      if (
        !resumeId &&
        answeredCount > 0 &&
        totalQuestions > 0 &&
        answeredCount >= totalQuestions
      ) {
        setStep("done");
        return;
      }

      if (resumeId && totalQuestions > 0) {
        const targetIndex = questions.findIndex((q) => q.id === resumeId);
        if (targetIndex >= 0) {
          setCurrentIndex(targetIndex);
        }
      } else if (!resumeId && answeredCount > 0 && totalQuestions > 0) {
        const nextIndex = Math.min(answeredCount, totalQuestions - 1);
        setCurrentIndex(nextIndex);
      }

      setStep("questions");
    } catch (err) {
      console.error(err);
      alert(err.message || "Unable to sign in");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAnswerSubmit = async (event) => {
    event.preventDefault();
    if (!motherId || !currentQuestion) return;

    const cachedValue = answeredCacheRef.current.get(currentQuestion.id);
    if (!isDirty && cachedValue) {
      if (currentIndex === questions.length - 1) {
        setStep("done");
      } else {
        setCurrentIndex((prev) => prev + 1);
      }
      return;
    }

    const answer = hasOptions ? selectedOption : textAnswer.trim();
    if (!answer) return;

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/answers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mother_id: motherId,
          question_id: currentQuestion.id,
          answer,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Unable to save answer");
      }

      answeredCacheRef.current.set(currentQuestion.id, answer);
      setIsDirty(false);

      if (currentIndex === questions.length - 1) {
        setStep("done");
      } else {
        setCurrentIndex((prev) => prev + 1);
      }
    } catch (err) {
      console.error(err);
      alert(err.message || "Unable to submit answer");
    } finally {
      setIsSubmitting(false);
    }
  };

  const showAuthForm = step === "auth";
  const isFinished = step === "done";

  const cachedAnswer = currentQuestion
    ? answeredCacheRef.current.get(currentQuestion.id)
    : null;

  const questionReady = hasOptions
    ? Boolean(selectedOption || (!isDirty && cachedAnswer))
    : Boolean(textAnswer.trim() || (!isDirty && cachedAnswer));

  const submitDisabled = showAuthForm
    ? authMode === "signup"
      ? !signupValid || isSubmitting
      : !loginValid || isSubmitting
    : isSubmitting || !currentQuestion || !questionReady;

  const buttonLabel = showAuthForm
    ? authMode === "signup"
      ? "Create account"
      : "Sign in"
    : currentIndex === questions.length - 1
      ? "Finish"
      : "Next";

  const progressLabel = showAuthForm
    ? authMode === "signup"
      ? "Step 1 of 2 · Create your Majka profile"
      : "Step 1 of 2 · Sign in to Majka"
    : questions.length
      ? `Question ${currentIndex + 1} of ${questions.length}`
      : "No questions available";

  const onSubmit =
    step === "auth"
      ? authMode === "signup"
        ? handleSignupSubmit
        : handleLoginSubmit
      : handleAnswerSubmit;

  return (
    <div className="app-container">
      <div className="card-wrapper">
        {!isFinished ? (
          <form className="uiverse-card" onSubmit={onSubmit}>
            <div className="card-header">
              <span className="chip">
                {showAuthForm
                  ? authMode === "signup"
                    ? "Join Majka"
                    : "Welcome back"
                  : "Majka Intake"}
              </span>
            </div>
            <div className="card-body">
              {showAuthForm ? (
                <>
                  <div className="auth-toggle">
                    <button
                      type="button"
                      className={authMode === "signup" ? "active" : ""}
                      onClick={() => setAuthMode("signup")}
                    >
                      Create account
                    </button>
                    <button
                      type="button"
                      className={authMode === "login" ? "active" : ""}
                      onClick={() => setAuthMode("login")}
                    >
                      Sign in
                    </button>
                  </div>
                  {authMode === "signup" ? (
                    <>
                      <h2 className="question-text">Hi! New Mama!</h2>
                      <div className="form-grid">
                        <label className="field">
                          <span>Name</span>
                          <input
                            className="text-input"
                            type="text"
                            value={signupForm.name}
                            placeholder="Your name"
                            onChange={(e) =>
                              handleSignupChange("name", e.target.value)
                            }
                            required
                          />
                        </label>
                        <label className="field">
                          <span>Password</span>
                          <input
                            className="text-input"
                            type="password"
                            value={signupForm.password}
                            placeholder="Create a password"
                            onChange={(e) =>
                              handleSignupChange("password", e.target.value)
                            }
                            required
                          />
                        </label>
                        <label className="field">
                          <span>Age</span>
                          <input
                            className="text-input"
                            type="number"
                            min="13"
                            value={signupForm.age}
                            placeholder="e.g. 32"
                            onChange={(e) =>
                              handleSignupChange("age", e.target.value)
                            }
                            required
                          />
                        </label>
                        <label className="field">
                          <span>Country</span>
                          <input
                            className="text-input"
                            type="text"
                            value={signupForm.country}
                            placeholder="Where are you?"
                            onChange={(e) =>
                              handleSignupChange("country", e.target.value)
                            }
                            required
                          />
                        </label>
                        <label className="field">
                          <span>When did you give birth?</span>
                          <input
                            className="text-input"
                            type="date"
                            value={signupForm.deliveredAt}
                            onChange={(e) =>
                              handleSignupChange("deliveredAt", e.target.value)
                            }
                            required
                          />
                        </label>
                      </div>
                    </>
                  ) : (
                    <>
                      <h2 className="question-text">Sign in Mama!</h2>
                      <div className="form-grid">
                        <label className="field">
                          <span>Name</span>
                          <input
                            className="text-input"
                            type="text"
                            value={loginForm.name}
                            placeholder="Registered name"
                            onChange={(e) =>
                              handleLoginChange("name", e.target.value)
                            }
                            required
                          />
                        </label>
                        <label className="field">
                          <span>Password</span>
                          <input
                            className="text-input"
                            type="password"
                            value={loginForm.password}
                            placeholder="Password"
                            onChange={(e) =>
                              handleLoginChange("password", e.target.value)
                            }
                            required
                          />
                        </label>
                      </div>
                    </>
                  )}
                </>
              ) : (
                <>
                  {isLoadingQuestions ? (
                    <p className="status-text">Loading questions...</p>
                  ) : fetchError ? (
                    <p className="status-text error">{fetchError}</p>
                  ) : currentQuestion ? (
                    <>
                      <h2 className="question-text">{currentQuestion.text}</h2>
                      {hasOptions ? (
                        <div className="option-list">
                          {currentQuestion.options.map((option) => (
                            <label
                              key={option.id}
                              className={`option-card ${
                                selectedOption === option.value ? "selected" : ""
                              }`}
                            >
                              <input
                                type="radio"
                                name={`question-${currentQuestion.id}`}
                                value={option.value}
                                checked={selectedOption === option.value}
                                onChange={(e) =>
                                  handleOptionSelect(e.target.value)
                                }
                              />
                              <span>{option.label}</span>
                            </label>
                          ))}
                        </div>
                      ) : (
                        <textarea
                          className="answer-input"
                          placeholder="Type your answer here."
                          value={textAnswer}
                          onChange={(e) => handleTextChange(e.target.value)}
                        />
                      )}
                    </>
                  ) : (
                    <p className="status-text">
                      No questions are available right now.
                    </p>
                  )}
                </>
              )}
            </div>
            <div className="card-footer">
              <div className="progress">{progressLabel}</div>
              {showAuthForm ? (
                <button type="submit" className="submit-btn" disabled={submitDisabled}>
                  {buttonLabel}
                </button>
              ) : (
                <div className="nav-buttons">
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={handlePrev}
                    disabled={currentIndex === 0 || isSubmitting}
                  >
                    Previous
                  </button>
                  <button type="submit" className="submit-btn" disabled={submitDisabled}>
                    {buttonLabel}
                  </button>
                </div>
              )}
            </div>
          </form>
        ) : (
          <div className="uiverse-card">
            <div className="card-body">
              <h2 className="question-text">Thank you from Majka 💗</h2>
              <p className="thankyou-text">
                Your profile and answers are saved. We&apos;ll tailor the next
                steps for you.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
