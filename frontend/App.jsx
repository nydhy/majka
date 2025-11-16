import { useState } from "react";
import "./App.css";

const QUESTIONS = [
  "When did you deliver your baby?",
  "Are you currently experiencing any pain or discomfort?",
  "How many minutes per day can you realistically move or exercise?",
  "How many weeks postpartum are you right now?"
];

function App() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [done, setDone] = useState(false);

  const question = QUESTIONS[currentIndex];

  const handleSubmit = async (e) => {
    e.preventDefault();

    const res = await fetch("http://localhost:8000/api/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        question,
        answer: currentAnswer
      })
    });

    const data = await res.json();
    if (!sessionId) setSessionId(data.session_id);

    setCurrentAnswer("");

    if (currentIndex === QUESTIONS.length - 1) {
      setDone(true);
    } else {
      setCurrentIndex(currentIndex + 1);
    }
  };

  return (
    <div className="app-container">
      <div className="card-wrapper">
        {!done ? (
          <form className="uiverse-card" onSubmit={handleSubmit}>
            <h2 className="question-text">{question}</h2>
            <textarea
              className="answer-input"
              placeholder="Type your answer…"
              value={currentAnswer}
              onChange={(e) => setCurrentAnswer(e.target.value)}
            />
            <button className="submit-btn" type="submit">
              {currentIndex === QUESTIONS.length - 1 ? "Finish" : "Next"}
            </button>
          </form>
        ) : (
          <div className="uiverse-card">
            <h2 className="question-text">Thank you 💕</h2>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
