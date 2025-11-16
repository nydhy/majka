import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import MajkaLogo from "./assets/Majka.png";
import AvatarPlaceholder from "./assets/woman.png";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const BOT_API_BASE = import.meta.env.VITE_BOT_API_URL || API_BASE;

const INITIAL_SIGNUP = {
  name: "",
  password: "",
  age: "",
  country: "",
  deliveredAt: "",
};

const INITIAL_LOGIN = { name: "", password: "" };

function App() {
  const [questions, setQuestions] = useState([]);
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(true);
  const [fetchError, setFetchError] = useState("");

  const [authMode, setAuthMode] = useState("signup"); // signup | login
  const [signupForm, setSignupForm] = useState(INITIAL_SIGNUP);
  const [loginForm, setLoginForm] = useState(INITIAL_LOGIN);
  const [motherName, setMotherName] = useState("");
  const [motherId, setMotherId] = useState(null);
  const [step, setStep] = useState("auth"); // auth | questions | done
  const [resumeQuestionId, setResumeQuestionId] = useState(null);

  const [currentIndex, setCurrentIndex] = useState(0);
  const answeredCacheRef = useRef(new Map());
  const prefillingRef = useRef(false);
  const [selectedOption, setSelectedOption] = useState("");
  const [textAnswer, setTextAnswer] = useState("");
  const [isDirty, setIsDirty] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [planStructured, setPlanStructured] = useState(null);
  const [planRaw, setPlanRaw] = useState("");
  const [planError, setPlanError] = useState("");
  const [planLoading, setPlanLoading] = useState(false);
  const [planRequested, setPlanRequested] = useState(false);
  const [sessionLoadingKey, setSessionLoadingKey] = useState("");
  const [sessionMessage, setSessionMessage] = useState("");
  const [sessionError, setSessionError] = useState("");
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [profileData, setProfileData] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [showRetakeConfirm, setShowRetakeConfirm] = useState(false);
  const [deliveredInputType, setDeliveredInputType] = useState("text");
  const [isVoiceBotOpen, setIsVoiceBotOpen] = useState(false);
  const [isMythOpen, setIsMythOpen] = useState(false);
  const [mythIndex, setMythIndex] = useState(0);
  const COUNTRY_LIST = useMemo(
    () => [
      "Afghanistan",
      "Albania",
      "Algeria",
      "Andorra",
      "Angola",
      "Antigua and Barbuda",
      "Argentina",
      "Armenia",
      "Australia",
      "Austria",
      "Azerbaijan",
      "Bahamas",
      "Bahrain",
      "Bangladesh",
      "Barbados",
      "Belarus",
      "Belgium",
      "Belize",
      "Benin",
      "Bhutan",
      "Bolivia",
      "Bosnia and Herzegovina",
      "Botswana",
      "Brazil",
      "Brunei",
      "Bulgaria",
      "Burkina Faso",
      "Burundi",
      "Cambodia",
      "Cameroon",
      "Canada",
      "Cape Verde",
      "Central African Republic",
      "Chad",
      "Chile",
      "China",
      "Colombia",
      "Comoros",
      "Congo (Brazzaville)",
      "Congo (Kinshasa)",
      "Costa Rica",
      "Croatia",
      "Cuba",
      "Cyprus",
      "Czech Republic",
      "Denmark",
      "Djibouti",
      "Dominica",
      "Dominican Republic",
      "Ecuador",
      "Egypt",
      "El Salvador",
      "Equatorial Guinea",
      "Eritrea",
      "Estonia",
      "Eswatini",
      "Ethiopia",
      "Fiji",
      "Finland",
      "France",
      "Gabon",
      "Gambia",
      "Georgia",
      "Germany",
      "Ghana",
      "Greece",
      "Grenada",
      "Guatemala",
      "Guinea",
      "Guinea-Bissau",
      "Guyana",
      "Haiti",
      "Honduras",
      "Hungary",
      "Iceland",
      "India",
      "Indonesia",
      "Iran",
      "Iraq",
      "Ireland",
      "Israel",
      "Italy",
      "Jamaica",
      "Japan",
      "Jordan",
      "Kazakhstan",
      "Kenya",
      "Kiribati",
      "Kuwait",
      "Kyrgyzstan",
      "Laos",
      "Latvia",
      "Lebanon",
      "Lesotho",
      "Liberia",
      "Libya",
      "Liechtenstein",
      "Lithuania",
      "Luxembourg",
      "Madagascar",
      "Malawi",
      "Malaysia",
      "Maldives",
      "Mali",
      "Malta",
      "Marshall Islands",
      "Mauritania",
      "Mauritius",
      "Mexico",
      "Micronesia",
      "Moldova",
      "Monaco",
      "Mongolia",
      "Montenegro",
      "Morocco",
      "Mozambique",
      "Myanmar",
      "Namibia",
      "Nauru",
      "Nepal",
      "Netherlands",
      "New Zealand",
      "Nicaragua",
      "Niger",
      "Nigeria",
      "North Korea",
      "North Macedonia",
      "Norway",
      "Oman",
      "Pakistan",
      "Palau",
      "Panama",
      "Papua New Guinea",
      "Paraguay",
      "Peru",
      "Philippines",
      "Poland",
      "Portugal",
      "Qatar",
      "Romania",
      "Russia",
      "Rwanda",
      "Saint Kitts and Nevis",
      "Saint Lucia",
      "Saint Vincent and the Grenadines",
      "Samoa",
      "San Marino",
      "Sao Tome and Principe",
      "Saudi Arabia",
      "Senegal",
      "Serbia",
      "Seychelles",
      "Sierra Leone",
      "Singapore",
      "Slovakia",
      "Slovenia",
      "Solomon Islands",
      "Somalia",
      "South Africa",
      "South Korea",
      "South Sudan",
      "Spain",
      "Sri Lanka",
      "Sudan",
      "Suriname",
      "Sweden",
      "Switzerland",
      "Syria",
      "Taiwan",
      "Tajikistan",
      "Tanzania",
      "Thailand",
      "Timor-Leste",
      "Togo",
      "Tonga",
      "Trinidad and Tobago",
      "Tunisia",
      "Turkey",
      "Turkmenistan",
      "Tuvalu",
      "Uganda",
      "Ukraine",
      "United Arab Emirates",
      "United Kingdom",
      "United States",
      "Uruguay",
      "Uzbekistan",
      "Vanuatu",
      "Vatican City",
      "Venezuela",
      "Vietnam",
      "Yemen",
      "Zambia",
      "Zimbabwe",
    ],
    []
  );
  const MYTHS = useMemo(
    () => [
      {
        myth: "You should bounce back quickly after birth.",
        fact:
          "Healing takes weeks to months—every body is different. Your uterus, pelvic floor, hormones, and heart need time. Forget bounce-back culture.",
      },
      {
        myth: "Postpartum ends after 6 weeks.",
        fact:
          "The 6-week checkup just confirms you're healing. Hormones, strength, and emotions shift for 12–18 months.",
      },
      {
        myth: "If you're not breastfeeding, you're failing.",
        fact:
          "Fed is best. Formula is healthy, your mental health matters, and you get to choose what's right for you.",
      },
      {
        myth: "Pelvic floor issues are normal—just live with them.",
        fact:
          "Leakage, heaviness, or pain are common but not normal. Pelvic PT and gentle exercises can fix most symptoms.",
      },
      {
        myth: "If it's painful, keep pushing through.",
        fact:
          "Postpartum exercise is gentle and pain-free. Pain means the body needs rest or support—pause and adjust.",
      },
      {
        myth: "You should love every moment with your newborn.",
        fact:
          "It's okay to feel overwhelmed or detached. Postpartum mood shifts affect 1 in 7 mothers and are treatable.",
      },
      {
        myth: "Your stomach will go back to normal quickly.",
        fact:
          "Ab separation needs months of careful rehab. Crunches or planks too soon can worsen it; slow core work wins.",
      },
      {
        myth: "Bleeding stops in a few days.",
        fact:
          "Lochia lasts 2–6 weeks and changes color. Sudden heavy bleeding is a warning sign—call your doctor.",
      },
      {
        myth: "You can't exercise until your doctor says so.",
        fact:
          "Unless you're told otherwise, gentle breathing, walking, and pelvic floor relaxation are safe within 24–48 hours.",
      },
      {
        myth: "As long as the baby is healthy, your feelings don't matter.",
        fact:
          "Your health matters too. Supporting mom's body and mind improves outcomes for both of you.",
      },
    ],
    []
  );

  const signupValid = useMemo(
    () =>
      signupForm.name.trim() &&
      signupForm.password.trim() &&
      signupForm.age.trim() &&
      signupForm.country.trim() &&
      signupForm.deliveredAt,
    [signupForm]
  );

  const loginValid = useMemo(
    () => loginForm.name.trim() && loginForm.password.trim(),
    [loginForm]
  );

  const resetPlanState = () => {
    setPlanStructured(null);
    setPlanRaw("");
    setPlanError("");
    setPlanLoading(false);
    setPlanRequested(false);
  };

  const fetchPlan = useCallback(async () => {
    if (!motherId) return;
    setPlanRequested(true);
    setPlanLoading(true);
    setPlanError("");
    try {
      const res = await fetch(`${API_BASE}/api/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mother_id: motherId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Unable to generate your plan");
      setPlanStructured(data.plan || null);
      setPlanRaw(data.plan_text || "");
    } catch (err) {
      console.error(err);
      setPlanError(err.message || "Unable to generate your plan");
    } finally {
      setPlanLoading(false);
    }
  }, [motherId]);

  const handleStartGuidedSession = useCallback(
    async (exercise) => {
      const title = exercise?.title;
      if (!title) return;
      setSessionError("");
      setSessionMessage("");
      setSessionLoadingKey(title);
      try {
        const res = await fetch(`${API_BASE}/api/guided-session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ exercise: title }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data?.detail || "Unable to launch guided session");
        }
        setSessionMessage(
          "Launching your Majka guided session window. Keep your webcam on!"
        );
      } catch (err) {
        console.error(err);
        setSessionError(err.message || "Unable to launch guided session");
      } finally {
        setSessionLoadingKey("");
      }
    },
    []
  );

  const handleToggleChat = () => {
    setIsChatOpen((prev) => !prev);
    setChatError("");
    if (!isChatOpen && chatMessages.length === 0) {
      setChatMessages([
        {
          role: "assistant",
          text: `Hi ${motherName || "mama"}! I’m Majka. Ask me anything about your plan, movement, or how you’re feeling.`,
        },
      ]);
    }
  };

  const handleSendChat = async (event) => {
    event?.preventDefault();
    const message = chatInput.trim();
    if (!message) return;
    const userMessage = { role: "user", text: message };
    setChatMessages((prev) => [...prev, userMessage]);
    setChatInput("");
    setChatLoading(true);
    setChatError("");
    try {
      const res = await fetch(`${BOT_API_BASE}/ask-majka`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: message,
          mother_id: motherId,
          mother_name: motherName,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || "Majka couldn't reply right now.");
      }
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", text: data.answer || "I'm here for you." },
      ]);
    } catch (err) {
      console.error(err);
      setChatError(err.message || "Majka couldn't reply right now.");
    } finally {
      setChatLoading(false);
    }
  };

  const handleOpenProfile = async () => {
    if (!motherId) return;
    setMenuOpen(false);
    setIsProfileOpen(true);
    setProfileError("");
    setProfileLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/mothers/${motherId}/profile`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Unable to load profile");
      setProfileData(data);
    } catch (err) {
      console.error(err);
      setProfileError(err.message || "Unable to load profile");
    } finally {
      setProfileLoading(false);
    }
  };

  const handleRetakeEvaluation = async () => {
    setMenuOpen(false);
    setShowRetakeConfirm(true);
  };

  const confirmRetake = async () => {
    if (!motherId) return;
    try {
      const res = await fetch(`${API_BASE}/api/mothers/${motherId}/retake`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || "Unable to reset answers");
      answeredCacheRef.current = new Map();
      setSelectedOption("");
      setTextAnswer("");
      setIsDirty(false);
      setResumeQuestionId(null);
      setCurrentIndex(0);
      setStep("questions");
      resetPlanState();
      setIsProfileOpen(false);
      setShowRetakeConfirm(false);
    } catch (err) {
      console.error(err);
      alert(err.message || "Unable to start retake");
    }
  };

  useEffect(() => {
    const loadQuestions = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/questions`);
        const data = await res.json();
        if (!res.ok) throw new Error(data?.detail || "Unable to load questions");
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
      setCurrentIndex(idx >= 0 ? idx : 0);
      return;
    }
    const answeredCount = answeredCacheRef.current.size;
    setCurrentIndex(answeredCount ? Math.min(answeredCount, questions.length - 1) : 0);
  }, [questions, resumeQuestionId]);

  useEffect(() => {
    if (
      step === "done" &&
      motherId &&
      !planRequested &&
      !planStructured &&
      !planRaw &&
      !planLoading &&
      !planError
    ) {
      fetchPlan();
    }
  }, [step, motherId, planRequested, planStructured, planRaw, planLoading, planError, fetchPlan]);

  useEffect(() => {
    if (step === "done" || !questions.length) return;
    if (!resumeQuestionId && answeredCacheRef.current.size >= questions.length) {
      setStep("done");
    }
  }, [questions, resumeQuestionId, step]);

  const loadCachedAnswer = (question) => {
    prefillingRef.current = true;
    const cachedValue = question ? answeredCacheRef.current.get(question.id) : null;
    if (!question || cachedValue === undefined) {
      setSelectedOption("");
      setTextAnswer("");
    } else if (question.options?.length) {
      const matchedOption = question.options.find(
        (opt) => opt.value === cachedValue || opt.label === cachedValue
      );
      if (matchedOption) {
        setSelectedOption(matchedOption.value);
        setTextAnswer("");
      } else {
        setTextAnswer(cachedValue);
        setSelectedOption("");
      }
    } else {
      setTextAnswer(cachedValue);
      setSelectedOption("");
    }
    prefillingRef.current = false;
    setIsDirty(false);
  };

  useEffect(() => {
    const active = questions[currentIndex];
    if (!active) return;
    loadCachedAnswer(active);
  }, [questions, currentIndex]);

  const handleSignupChange = (field, value) =>
    setSignupForm((prev) => ({ ...prev, [field]: value }));
  const handleLoginChange = (field, value) =>
    setLoginForm((prev) => ({ ...prev, [field]: value }));

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

  const commonSignupPayload = () => ({
    name: signupForm.name.trim(),
    password: signupForm.password,
    age: signupForm.age ? Number(signupForm.age) : null,
    country: signupForm.country.trim(),
    delivered_at: signupForm.deliveredAt
      ? new Date(signupForm.deliveredAt).toISOString()
      : null,
  });

  const handleSignupSubmit = async (event) => {
    event.preventDefault();
    if (!signupValid) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/mothers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(commonSignupPayload()),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Unable to create your Majka profile");
      setMotherId(data.mother_id);
      setMotherName(signupForm.name.trim());
      setResumeQuestionId(null);
      answeredCacheRef.current = new Map();
      setSelectedOption("");
      setTextAnswer("");
      setIsDirty(false);
      resetPlanState();
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
      if (!res.ok) throw new Error(data?.detail || "Invalid name or password");
      setMotherId(data.mother_id);
      setMotherName(data.profile?.name || loginForm.name.trim());
      const answeredEntries = Object.entries(data.answered_answers || {}).map(
        ([key, value]) => [Number(key), value]
      );
      answeredCacheRef.current = new Map(answeredEntries);
      setResumeQuestionId(data.resume_question_id ?? null);
      resetPlanState();
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
    const activeQuestion = questions[currentIndex];
    if (!motherId || !activeQuestion) return;
    const cachedValue = answeredCacheRef.current.get(activeQuestion.id);
    if (!isDirty && cachedValue !== undefined) {
      if (currentIndex === questions.length - 1) {
        resetPlanState();
        setStep("done");
      } else {
        setCurrentIndex((prev) => prev + 1);
      }
      return;
    }

    let answer = textAnswer.trim();
    if (activeQuestion.options?.length) {
      const matchedOption = activeQuestion.options.find(
        (opt) => opt.value === selectedOption || opt.label === selectedOption
      );
      answer = matchedOption ? matchedOption.label : "";
    }
    if (!answer) return;

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/answers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mother_id: motherId,
          question_id: activeQuestion.id,
          answer,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Unable to save answer");
      answeredCacheRef.current.set(activeQuestion.id, answer);
      setIsDirty(false);
      if (currentIndex === questions.length - 1) {
        resetPlanState();
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
  const activeQuestion = questions[currentIndex];
  const hasOptions = activeQuestion?.options?.length > 0;

  const questionReady = hasOptions
    ? Boolean(selectedOption)
    : Boolean(textAnswer.trim());

  const submitDisabled = showAuthForm
    ? authMode === "signup"
      ? !signupValid || isSubmitting
      : !loginValid || isSubmitting
    : isSubmitting || !activeQuestion || !questionReady;

  const buttonLabel = showAuthForm
    ? authMode === "signup"
      ? "Start Intake"
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

  const planGreeting =
    (planStructured?.greeting ||
      (motherName ? `Hello mama ${motherName}, it's Majka here!` : "Hello mama, it's Majka here!")) +
    "💗";

  return (
    <div className="app-container">
      <div className="card-wrapper">
        {!isFinished ? (
          <form
            className="uiverse-card"
            onSubmit={
              showAuthForm
                ? authMode === "signup"
                  ? handleSignupSubmit
                  : handleLoginSubmit
                : handleAnswerSubmit
            }
          >
            <div className="card-header">
              <img src={MajkaLogo} alt="Majka logo" className="logo-mark" />
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
                      <h2 className="question-text">Hello Mama!</h2>
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
                          <select
                            className="text-input"
                            value={signupForm.country}
                            onChange={(e) =>
                              handleSignupChange("country", e.target.value)
                            }
                            required
                          >
                            <option value="">Select your country</option>
                            {COUNTRY_LIST.map((country) => (
                              <option key={country} value={country}>
                                {country}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span>When did you give birth?</span>
                          <input
                            className="text-input"
                            type={deliveredInputType}
                            placeholder="MM-DD-YYYY"
                            value={signupForm.deliveredAt}
                            onFocus={() => setDeliveredInputType("date")}
                            onBlur={(e) => {
                              if (!e.target.value) {
                                setDeliveredInputType("text");
                              }
                            }}
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
                      <h2 className="question-text">Welcome back Mama!</h2>
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
                  ) : activeQuestion ? (
                    <>
                      <h2 className="question-text">{activeQuestion.text}</h2>
                      {hasOptions ? (
                        <div className="option-list">
                          {activeQuestion.options.map((option) => (
                            <label
                              key={option.id}
                              className={`option-card ${
                                selectedOption === option.value ? "selected" : ""
                              }`}
                            >
                              <input
                                type="radio"
                                name={`question-${activeQuestion.id}`}
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
              <div className="plan-section">
                {sessionMessage && (
                  <p className="session-feedback success">{sessionMessage}</p>
                )}
                {sessionError && (
                  <p className="session-feedback error">{sessionError}</p>
                )}
                {planLoading ? (
                  <div className="plan-loading">
                    <p>Crafting your personalized flow...</p>
                    <div className="loading-dots">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                ) : planError ? (
                  <div className="plan-error">
                    <p>{planError}</p>
                    <button
                      type="button"
                      className="secondary-btn"
                      onClick={fetchPlan}
                      disabled={planLoading}
                    >
                      Try again
                    </button>
                  </div>
                ) : planStructured ? (
                  <div className="plan-structured">
                    <p className="plan-greeting">{planGreeting}</p>
                    {planStructured.intro && (
                      <p className="plan-intro">{planStructured.intro}</p>
                    )}
                    <div className="plan-cards">
                      {(planStructured.exercises || []).map((exercise, idx) => (
                        <div className="exercise-card" key={`exercise-${idx}`}>
                          <div className="exercise-copy">
                            <h3>{exercise.title}</h3>
                            {exercise.summary && <p>{exercise.summary}</p>}
                            {exercise.why && (
                              <p className="exercise-meta">
                                <strong>Why it fits:</strong> {exercise.why}
                              </p>
                            )}
                            {exercise.how && (
                              <p className="exercise-meta">
                                <strong>How to try it:</strong> {exercise.how}
                              </p>
                            )}
                          </div>
                          <button
                            type="button"
                            className="pink-cta"
                            onClick={() => handleStartGuidedSession(exercise)}
                            disabled={sessionLoadingKey === exercise.title}
                          >
                            {sessionLoadingKey === exercise.title
                              ? "Launching..."
                              : exercise.cta_label || "Start Guided Session"}
                          </button>
                        </div>
                      ))}
                    </div>
                    {planStructured.closing && (
                      <p className="plan-closing">{planStructured.closing}</p>
                    )}
                  </div>
                ) : planRaw ? (
                  <div className="plan-result">
                    {planRaw
                      .split(/\n+/)
                      .filter((para) => para.trim().length)
                      .map((para, idx) => (
                        <p key={`plan-line-${idx}`}>{para}</p>
                      ))}
                  </div>
                ) : (
                  <div className="plan-placeholder">
                    <p>We&apos;ll show your personalized flow as soon as it&apos;s ready.</p>
                    <button
                      type="button"
                      className="secondary-btn"
                      onClick={fetchPlan}
                      disabled={planLoading}
                    >
                      Refresh plan
                    </button>
                  </div>
                )}
              </div>
              <div className="plan-branding">
                <img src={MajkaLogo} alt="Majka logo" className="logo-badge" />
                <span>Majka · Gentle Strength for Mamas</span>
              </div>
            </div>
          </div>
        )}
      </div>
      {isFinished && (
        <>
          <button
            type="button"
            className="chat-launcher"
            onClick={handleToggleChat}
            aria-label={isChatOpen ? "Close Majka Chat" : "Chat with Majka"}
          >
            <img src={MajkaLogo} alt="" className="chat-launcher__logo" />
          </button>
          {isChatOpen && (
            <div className="chat-panel">
              <div className="chat-head">
                <div>
                  <p className="chat-title">Ask Majka</p>
                  <p className="chat-subtitle">Your gentle companion</p>
                </div>
                <button
                  type="button"
                  className="chat-close"
                  onClick={handleToggleChat}
                >
                  ×
                </button>
              </div>
              <div className="chat-body">
                {chatMessages.map((msg, idx) => (
                  <div
                    key={`chat-${idx}-${msg.role}`}
                    className={`chat-bubble ${msg.role}`}
                  >
                    {msg.text}
                  </div>
                ))}
                {chatLoading && (
                  <div className="chat-bubble assistant">Typing…</div>
                )}
                {chatError && <p className="chat-error">{chatError}</p>}
              </div>
              <form className="chat-input-row" onSubmit={handleSendChat}>
                <input
                  type="text"
                  value={chatInput}
                  placeholder="Ask Majka anything…"
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={chatLoading}
                />
                <button type="submit" disabled={chatLoading || !chatInput.trim()}>
                  Send
                </button>
              </form>
            </div>
          )}
        </>
      )}
      {motherId && !showAuthForm && (
        <div className="floating-menu">
          <button
            type="button"
            className="hamburger-btn"
            onClick={() => setMenuOpen((prev) => !prev)}
            aria-label="Majka menu"
          >
            <span />
            <span />
            <span />
          </button>
          {menuOpen && (
            <div className="menu-dropdown floating">
              <button type="button" onClick={handleOpenProfile}>
                Profile
              </button>
                      <button type="button" onClick={handleRetakeEvaluation}>
                        Retake Evaluation
                      </button>
                      <button type="button" onClick={() => setIsVoiceBotOpen(true)}>
                        VoiceBot (Majka)
                      </button>
                      <button type="button" onClick={() => setIsMythOpen(true)}>
                        Myth Buster
                      </button>
                    </div>
                  )}
                </div>
              )}
      {isProfileOpen && (
        <div className="profile-overlay">
          <div className="profile-panel">
            <div className="profile-head">
              <h3>Profile</h3>
              <button
                type="button"
                className="profile-close"
                onClick={() => setIsProfileOpen(false)}
                aria-label="Close profile"
              >
                ×
              </button>
            </div>
            {profileLoading ? (
              <p className="status-text">Loading profile...</p>
            ) : profileError ? (
              <p className="status-text error">{profileError}</p>
            ) : profileData ? (
              <>
                <div className="profile-info">
                  <div className="profile-avatar" aria-hidden="true">
                    <img src={AvatarPlaceholder} alt="" />
                  </div>
                  <div className="profile-meta-block">
                    <p className="profile-name">
                      {profileData.profile?.name || "Majka Mama"}
                    </p>
                    <p className="profile-meta">
                      {profileData.profile?.country || "Somewhere comfy"}
                    </p>
                    <p className="profile-meta">
                      Delivery:
                      {" "}
                    {profileData.profile?.delivered_at
                      ? new Date(
                          profileData.profile.delivered_at
                        ).toLocaleDateString("en-US", {
                          month: "2-digit",
                          day: "2-digit",
                          year: "numeric",
                        })
                      : "Not provided"}
                    </p>
                  </div>
                </div>
                <div className="profile-answers scrollable">
                  <h4>Your Answers</h4>
                  {profileData.answers?.length ? (
                    profileData.answers.map((item) => (
                      <div
                        key={`${item.order_index}-${item.question}`}
                        className="profile-answer-card"
                      >
                        <p className="question-label">{item.question}</p>
                        <p className="answer-value">{item.answer}</p>
                      </div>
                    ))
                  ) : (
                    <p className="status-text">No answers recorded yet.</p>
                  )}
                </div>
              </>
            ) : (
              <p className="status-text">No profile data yet.</p>
            )}
          </div>
        </div>
      )}
      {showRetakeConfirm && (
        <div className="profile-overlay">
          <div className="retake-modal">
            <h3>Retake Evaluation?</h3>
            <p>
              Choosing this will reset your answers and might change the
              exercises Majka suggests. Do you want to proceed?
            </p>
            <div className="retake-actions">
              <button
                type="button"
                className="retake-cancel"
                onClick={() => setShowRetakeConfirm(false)}
              >
                Go Back
              </button>
              <button
                type="button"
                className="retake-proceed"
                onClick={confirmRetake}
              >
                Proceed
              </button>
            </div>
          </div>
        </div>
      )}
      {isVoiceBotOpen && (
        <div className="profile-overlay">
          <div className="voicebot-panel">
            <button
              type="button"
              className="profile-close voicebot-close"
              onClick={() => setIsVoiceBotOpen(false)}
            >
              ×
            </button>
            <div className="voice-logo">
              <img src={MajkaLogo} alt="Majka voicebot" />
              <div className="voice-pulse pulse-1" />
              <div className="voice-pulse pulse-2" />
            </div>
            <p className="voicebot-text">
              Majka is listening. Ask your question when you're ready.
            </p>
            <button
              type="button"
              className="retake-proceed"
              onClick={async () => {
                await new Promise((resolve) => setTimeout(resolve, 1500));
                alert("VoiceBot is still under development, stay tuned!");
              }}
            >
              Start VoiceBot
            </button>
          </div>
        </div>
      )}
      {isMythOpen && (
        <div className="profile-overlay">
          <div className="myth-panel">
            <button
              type="button"
              className="profile-close myth-close"
              onClick={() => setIsMythOpen(false)}
            >
              ×
            </button>
            <h3>Majka Myth Buster</h3>
            <div className="myth-card">
              <p className="myth-label">Myth</p>
              <p className="myth-text">{MYTHS[mythIndex].myth}</p>
              <p className="fact-label">Fact</p>
              <p className="fact-text">{MYTHS[mythIndex].fact}</p>
            </div>
            <div className="myth-controls">
              <button
                type="button"
                className="secondary-btn"
                onClick={() =>
                  setMythIndex((prev) => (prev - 1 + MYTHS.length) % MYTHS.length)
                }
              >
                ← Prev
              </button>
              <button
                type="button"
                className="secondary-btn"
                onClick={() =>
                  setMythIndex((prev) => (prev + 1) % MYTHS.length)
                }
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

