import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [questions, setQuestions] = useState([]);
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(true);
  const [fetchError, setFetchError] = useState("");

  const [motherForm, setMotherForm] = useState({
    name: "",
    age: "",
    country: "",
    deliveredAt: "",
  });
  const [motherId, setMotherId] = useState(null);
  const [step, setStep] = useState("mother");

  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState("");
  const [textAnswer, setTextAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  const currentQuestion = questions[currentIndex];
  const hasOptions = currentQuestion?.options?.length > 0;

  const motherFormValid = useMemo(() => {
    return (
      motherForm.name.trim() &&
      motherForm.age.trim() &&
      motherForm.country.trim() &&
      motherForm.deliveredAt
    );
  }, [motherForm]);

  const handleMotherChange = (field, value) => {
    setMotherForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleMotherSubmit = async (event) => {
    event.preventDefault();
    if (!motherFormValid) return;

    setIsSubmitting(true);
    try {
      const payload = {
        name: motherForm.name.trim(),
        age: motherForm.age ? Number(motherForm.age) : null,
        country: motherForm.country.trim(),
        delivered_at: motherForm.deliveredAt
          ? new Date(motherForm.deliveredAt).toISOString()
          : null,
      };

      const res = await fetch(`${API_BASE}/api/mothers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Unable to save your profile");
      }

      setMotherId(data.mother_id);
      setStep("questions");
    } catch (err) {
      console.error(err);
      alert(err.message || "Unable to start intake");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAnswerSubmit = async (event) => {
    event.preventDefault();
    if (!motherId || !currentQuestion) return;

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

      if (currentIndex === questions.length - 1) {
        setStep("done");
      } else {
        setCurrentIndex((prev) => prev + 1);
        setSelectedOption("");
        setTextAnswer("");
      }
    } catch (err) {
      console.error(err);
      alert(err.message || "Unable to submit answer");
    } finally {
      setIsSubmitting(false);
    }
  };

  const showMotherForm = step === "mother";
  const isFinished = step === "done";

  const submitDisabled = showMotherForm
    ? !motherFormValid || isSubmitting
    : isSubmitting || !currentQuestion || (!hasOptions && !textAnswer.trim()) || (hasOptions && !selectedOption);

  const buttonLabel = showMotherForm
    ? "Start Intake"
    : currentIndex === questions.length - 1
      ? "Finish"
      : "Next";

  return (
    <div className="app-container">
      <div className="card-wrapper">
        {!isFinished ? (
          <form
            className="uiverse-card"
            onSubmit={showMotherForm ? handleMotherSubmit : handleAnswerSubmit}
          >
            <div className="card-header">
              <span className="chip">{showMotherForm ? "About you" : "Majka Intake"}</span>
            </div>
            <div className="card-body">
              {showMotherForm ? (
                <>
                  <h2 className="question-text">Let&apos;s get to know you</h2>
                  <div className="form-grid">
                    <label className="field">
                      <span>Name</span>
                      <input
                        className="text-input"
                        type="text"
                        value={motherForm.name}
                        placeholder="Your name"
                        onChange={(e) =>
                          handleMotherChange("name", e.target.value)
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
                        value={motherForm.age}
                        placeholder="e.g. 32"
                        onChange={(e) =>
                          handleMotherChange("age", e.target.value)
                        }
                        required
                      />
                    </label>
                    <label className="field">
                      <span>Country</span>
                      <input
                        className="text-input"
                        type="text"
                        value={motherForm.country}
                        placeholder="Where are you?"
                        onChange={(e) =>
                          handleMotherChange("country", e.target.value)
                        }
                        required
                      />
                    </label>
                    <label className="field">
                      <span>When did you give birth?</span>
                      <input
                        className="text-input"
                        type="date"
                        value={motherForm.deliveredAt}
                        onChange={(e) =>
                          handleMotherChange("deliveredAt", e.target.value)
                        }
                        required
                      />
                    </label>
                  </div>
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
                                  setSelectedOption(e.target.value)
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
                          onChange={(e) => setTextAnswer(e.target.value)}
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
              <div className="progress">
                {showMotherForm
                  ? "Step 1 of 2"
                  : `Question ${currentIndex + 1} of ${questions.length}`}
              </div>
              <button type="submit" className="submit-btn" disabled={submitDisabled}>
                {buttonLabel}
              </button>
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
