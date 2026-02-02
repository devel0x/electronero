export type Role =
  | "admin"
  | "judge"
  | "participant"
  | "voter"
  | "moderator"
  | "auditor"
  | "sponsor";

export type Season = {
  sid: string;
  status: string;
  created_at: string;
  ends_at?: string;
};

export type Submission = {
  sub_id: string;
  uid: string;
  threads_url: string;
  code_phrase: string;
  status: string;
  created_at: string;
  review_notes?: string;
  agg_score?: number;
};

export type LeaderboardEntry = {
  sub_id: string;
  uid: string;
  username: string;
  threads_url: string;
  status: string;
  score: number;
};
