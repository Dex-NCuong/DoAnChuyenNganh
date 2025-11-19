import { api } from "./api";

// Generate quiz from document
export async function generateQuiz(
  documentId,
  numQuestions = 10,
  difficulty = "medium",
  questionTypes = ["multiple_choice", "true_false"]
) {
  const { data } = await api.post("/quiz/generate", {
    document_id: documentId,
    num_questions: numQuestions,
    difficulty,
    question_types: questionTypes,
  });
  return data;
}

// List quizzes
export async function listQuizzes(documentId = null, limit = 20) {
  const params = { limit };
  if (documentId) params.document_id = documentId;
  const { data } = await api.get("/quiz/", { params });
  return data;
}

// Get quiz by ID
export async function getQuiz(quizId) {
  const { data } = await api.get(`/quiz/${quizId}`);
  return data;
}

// Delete quiz
export async function deleteQuiz(quizId) {
  await api.delete(`/quiz/${quizId}`);
}

// Submit quiz attempt
export async function submitQuiz(quizId, mode, answers, timeTaken = null) {
  const { data } = await api.post("/quiz/submit", {
    quiz_id: quizId,
    mode,
    answers,
    time_taken: timeTaken,
  });
  return data;
}

// List quiz attempts
export async function listQuizAttempts(quizId = null, limit = 20) {
  const params = { limit };
  if (quizId) params.quiz_id = quizId;
  const { data } = await api.get("/quiz/attempts/history", { params });
  return data;
}

