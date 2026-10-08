export type Role = "SUPER_ADMIN" | "CONTENT_ADMIN" | "USER";

export interface User {
  id: number;
  email: string;
  full_name?: string | null;
  role: Role;
  organization_id?: number | null;
  is_active: boolean;
  created_at?: string | null;
}

export const isAdmin = (user: User | null): boolean =>
  !!user && (user.role === "SUPER_ADMIN" || user.role === "CONTENT_ADMIN");

export interface Citation {
  document_id?: number | null;
  document_version_id?: number | null;
  chunk_id?: number | null;
  document_title?: string | null;
  version?: string | null;
  section?: string | null;
  heading?: string | null;
  page?: number | null;
  relevance?: number | null;
  snippet?: string | null;
}

export interface Message {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  mode?: string | null;
  error?: string | null;
  created_at?: string | null;
  citations: Citation[];
}

export interface Conversation {
  id: number;
  title: string;
  mode: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface ChatModeInfo {
  value: string;
  label: string;
  available: boolean;
}

export interface DocumentVersion {
  id: number;
  version_label: string;
  is_active: boolean;
  processing_status: string;
  processing_error?: string | null;
  page_count?: number | null;
  chunk_count?: number | null;
  original_filename?: string | null;
  created_at?: string | null;
}

export interface DocumentItem {
  id: number;
  title: string;
  description?: string | null;
  category?: string | null;
  department?: string | null;
  doc_type?: string | null;
  status: string;
  active_version_label?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  versions?: DocumentVersion[];
}

export interface LearningSession {
  id: number;
  topic_name: string;
  status: string;
  current_section?: string | null;
  total_sections: number;
  completed_sections: number;
  questions_answered: number;
  correct_answers: number;
  created_at?: string | null;
}

export interface QuizQuestion {
  id: number;
  prompt: string;
  question_type: string;
  options: string[];
  difficulty?: string | null;
  citations?: Citation[];
}

export interface ExamQuestion {
  id: number;
  prompt: string;
  question_type: string;
  options: string[];
  difficulty?: string | null;
  citations?: Citation[];
}

export interface ExamStart {
  attempt_id: number;
  exam: {
    id: number;
    topic_label?: string | null;
    difficulty: string;
    question_count: number;
    time_limit_minutes: number;
    question_type: string;
  };
  questions: ExamQuestion[];
  expires_at?: string | null;
}

export interface ExamResult {
  attempt_id: number;
  score: number;
  maximum_score: number;
  percentage: number;
  weak_topics: string[];
  details: {
    question_id: number;
    prompt: string;
    your_answer: string | null;
    correct_answer: string | null;
    is_correct: boolean;
    explanation: string | null;
    topic: string | null;
    sources?: Citation[];
  }[];
}

export interface InterviewSession {
  id: number;
  job_title: string;
  industry?: string | null;
  experience_level?: string | null;
  interview_type: string;
  status: string;
  created_at?: string | null;
}

export interface InterviewQuestion {
  id: number;
  order_index: number;
  prompt: string;
  question_type: string;
  citations?: Citation[];
}

export interface UserDashboard {
  stats: Record<string, number>;
  weak_topics: string[];
  recommended_topics: string[];
  recent_conversations: { id: number; label: string; detail?: string | null; at?: string | null }[];
  recent_learning: { id: number; label: string; detail?: string | null; at?: string | null }[];
  exam_attempts: { id: number; status: string; score: number; maximum_score: number; percentage?: number | null; at?: string | null }[];
  interview_sessions: { id: number; job_title: string; status: string; at?: string | null }[];
}

export interface AdminDashboard {
  totals: Record<string, number>;
  documents: Record<string, number>;
  engagement: Record<string, number>;
  recent_documents: { id: number; title: string; status: string; department?: string | null; created_at?: string | null }[];
}
