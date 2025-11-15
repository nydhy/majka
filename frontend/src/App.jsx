import { useState } from "react";
import "./App.css";

const QUESTIONS = [
  "When did you deliver your baby?",
  "Are you currently experiencing any pain or discomfort?",
  "How many minutes per day can you realistically move or exercise?",
  "How many weeks postpartum are you right now?",
];

function App() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [done, setDone] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const question = QUESTIONS[currentIndex];

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!currentAnswer.trim()) return;

    setIsSubmitting(true);
    try {
      const res = await fetch("http://localhost:8000/api/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          question,
          answer: currentAnswer,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        console.error(data);
        alert("Backend error");
        return;
      }

      if (!sessionId) setSessionId(data.session_id);
      setCurrentAnswer("");

      if (currentIndex === QUESTIONS.length - 1) {
        setDone(true);
      } else {
        setCurrentIndex((prev) => prev + 1);
      }
    } catch (err) {
      console.error(err);
      alert("Network error – is the backend running on :8000?");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="app-container">
      <div className="card-wrapper">
        {!done ? (
          <form className="uiverse-card" onSubmit={handleSubmit}>
            <div className="card-header">
              <span className="chip">Postpartum Intake</span>
            </div>
            <div className="card-body">
              <h2 className="question-text">{question}</h2>
              <textarea
                className="answer-input"
                placeholder="Type your answer here…"
                value={currentAnswer}
                onChange={(e) => setCurrentAnswer(e.target.value)}
              />
            </div>
            <div className="card-footer">
              <div className="progress">
                Question {currentIndex + 1} of {QUESTIONS.length}
              </div>
              <button
                type="submit"
                className="submit-btn"
                disabled={isSubmitting || !currentAnswer.trim()}
              >
                {currentIndex === QUESTIONS.length - 1 ? "Finish" : "Next"}
              </button>
            </div>
          </form>
        ) : (
          <div className="uiverse-card">
            <div className="card-body">
              <h2 className="question-text">Thank you, mama 💕</h2>
              <p className="thankyou-text">
                Your answers are safely saved. We’ll use them to personalize
                your postpartum journey.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
