-- LegalEase production-ready relational model (MySQL 8+).
-- The runnable classroom demo uses SQLite with the same ownership relationships.

CREATE TABLE users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('member', 'admin') NOT NULL DEFAULT 'member',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE documents (
  id CHAR(36) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  filename VARCHAR(255) NOT NULL,
  stored_path VARCHAR(500) NULL,
  mime_type VARCHAR(120) NOT NULL,
  extracted_text LONGTEXT NOT NULL,
  summary TEXT NOT NULL,
  analysis_json JSON NOT NULL,
  status ENUM('queued', 'extracting', 'analyzing', 'ready', 'failed') NOT NULL DEFAULT 'queued',
  engine VARCHAR(80) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_documents_owner_created (user_id, created_at DESC),
  CONSTRAINT fk_documents_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Optional extension tables for a deployed multi-worker version:
CREATE TABLE document_clauses (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  document_id CHAR(36) NOT NULL,
  category VARCHAR(60) NOT NULL,
  risk_level ENUM('High', 'Medium', 'Low') NOT NULL,
  risk_score TINYINT UNSIGNED NOT NULL,
  source_start INT NULL,
  source_end INT NULL,
  explanation TEXT NOT NULL,
  next_step TEXT NOT NULL,
  PRIMARY KEY (id),
  KEY idx_clauses_document_risk (document_id, risk_level),
  CONSTRAINT fk_clauses_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
