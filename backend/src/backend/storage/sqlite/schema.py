import threading

from backend.storage.sqlite.migrations import migrate_schema
from backend.storage.sqlite.uow import unit_of_work

CURRENT_SCHEMA_VERSION = 19

_init_lock = threading.RLock()


def init_db() -> None:
    """Thread-safe schema initialization and migration."""
    with _init_lock, unit_of_work() as conn:
        current_version = conn.execute("PRAGMA user_version").fetchone()[0]
        if current_version < 1:
            # Fresh database: the initial schema already matches the current
            # version, so no incremental migration must run on top of it.
            _create_initial_schema(conn)
            conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        elif current_version < CURRENT_SCHEMA_VERSION:
            migrate_schema(conn, current_version)
            conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")


def _create_initial_schema(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY,
          username TEXT NOT NULL UNIQUE,
          hashed_password TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS papers (
          id TEXT PRIMARY KEY,
          user_id TEXT NULL,
          title TEXT NOT NULL,
          authors_json TEXT NULL,
          year INTEGER NULL,
          venue TEXT NULL,
          doi TEXT NULL,
          arxiv_id TEXT NULL,
          abstract TEXT NULL,
          url TEXT NULL,
          metadata_json TEXT NULL,
          reading_status TEXT NOT NULL DEFAULT 'inbox',
          progress REAL NOT NULL DEFAULT 0,
          last_location_json TEXT NULL,
          last_read_at TEXT NULL,
          time_spent_seconds INTEGER NOT NULL DEFAULT 0,
          last_citation_count INTEGER NULL,
          last_arxiv_updated TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          CHECK (reading_status IN ('inbox', 'queued', 'skimming', 'reading', 'read', 'archived')),
          CHECK (progress >= 0 AND progress <= 1)
        );

        CREATE TABLE IF NOT EXISTS collections (
          id TEXT PRIMARY KEY,
          user_id TEXT NULL,
          name TEXT NOT NULL,
          description TEXT NULL,
          sort_order INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          user_id TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          last_opened_at TEXT NOT NULL,
          is_archived INTEGER NOT NULL DEFAULT 0,
          is_pinned INTEGER NOT NULL DEFAULT 0,
          paper_id TEXT NULL REFERENCES papers(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
          id TEXT PRIMARY KEY,
          paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          filename TEXT NOT NULL,
          file_path TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          file_size INTEGER NOT NULL,
          file_hash TEXT NULL,
          chunk_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          error_message TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          parsed_ir_path TEXT NULL,
          parsed_markdown_path TEXT NULL,
          quality_report_path TEXT NULL,
          parser_name TEXT NULL,
          parser_version TEXT NULL,
          parse_quality_status TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS chunks (
          id TEXT PRIMARY KEY,
          paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          section TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          text_excerpt TEXT NOT NULL,
          text_content TEXT NOT NULL,
          type TEXT NOT NULL,
          created_at TEXT NOT NULL,
          section_path_json TEXT NULL,
          page_start INTEGER NULL,
          page_end INTEGER NULL,
          bbox_json TEXT NULL,
          block_ids_json TEXT NULL,
          block_types_json TEXT NULL,
          linked_block_ids_json TEXT NULL,
          confidence REAL NULL
        );

        CREATE TABLE IF NOT EXISTS retrieval_indexes (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          index_path TEXT NOT NULL,
          chunks_path TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY,
          paper_id TEXT NULL REFERENCES papers(id) ON DELETE CASCADE,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          document_id TEXT NULL REFERENCES documents(id) ON DELETE SET NULL,
          type TEXT NOT NULL,
          status TEXT NOT NULL,
          stage TEXT NOT NULL,
          attempt INTEGER NOT NULL DEFAULT 0,
          error_message TEXT NULL,
          payload_json TEXT NULL,
          created_at TEXT NOT NULL,
          started_at TEXT NULL,
          finished_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS index_snapshots (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          status TEXT NOT NULL,
          index_path TEXT NOT NULL,
          chunks_path TEXT NOT NULL,
          document_ids_json TEXT NOT NULL,
          embedding_fingerprint TEXT NULL,
          embedding_model TEXT NULL,
          error_message TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          sources_json TEXT NULL,
          status TEXT NOT NULL,
          client_message_id TEXT NULL,
          model TEXT NULL,
          prompt_tokens INTEGER NULL,
          completion_tokens INTEGER NULL,
          created_at TEXT NOT NULL,
          run_id TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          user_id TEXT NULL,
          client_message_id TEXT NULL,
          status TEXT NOT NULL,
          model TEXT NULL,
          max_steps INTEGER NOT NULL DEFAULT 12,
          step_count INTEGER NOT NULL DEFAULT 0,
          prompt_tokens INTEGER NULL,
          completion_tokens INTEGER NULL,
          error_message TEXT NULL,
          created_at TEXT NOT NULL,
          finished_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_steps (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
          step_index INTEGER NOT NULL,
          kind TEXT NOT NULL,
          tool_name TEXT NULL,
          arguments_json TEXT NULL,
          result_json TEXT NULL,
          sources_json TEXT NULL,
          summary TEXT NULL,
          status TEXT NOT NULL,
          error_message TEXT NULL,
          latency_ms INTEGER NULL,
          prompt_tokens INTEGER NULL,
          completion_tokens INTEGER NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS annotations (
          id TEXT PRIMARY KEY,
          paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
          document_id TEXT NULL REFERENCES documents(id) ON DELETE SET NULL,
          chunk_id TEXT NULL REFERENCES chunks(id) ON DELETE SET NULL,
          type TEXT NOT NULL,
          quote TEXT NULL,
          content TEXT NULL,
          color TEXT NULL,
          page_start INTEGER NULL,
          page_end INTEGER NULL,
          bbox_json TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          CHECK (type IN ('highlight', 'note', 'question'))
        );

        CREATE TABLE IF NOT EXISTS collection_papers (
          collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
          paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
          added_at TEXT NOT NULL,
          sort_order INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (collection_id, paper_id)
        );

        CREATE TABLE IF NOT EXISTS paper_tags (
          paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
          tag TEXT NOT NULL,
          PRIMARY KEY (paper_id, tag)
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
          id TEXT PRIMARY KEY,
          user_id TEXT NULL,
          kind TEXT NOT NULL,
          value TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'arxiv',
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          last_checked_at TEXT NULL,
          CHECK (kind IN ('keyword', 'author', 'venue', 'institution'))
        );

        CREATE TABLE IF NOT EXISTS feed_items (
          id TEXT PRIMARY KEY,
          user_id TEXT NULL,
          source TEXT NOT NULL,
          external_id TEXT NOT NULL,
          title TEXT NOT NULL,
          authors_json TEXT NULL,
          abstract TEXT NULL,
          url TEXT NULL,
          published_at TEXT NULL,
          paper_id TEXT NULL REFERENCES papers(id) ON DELETE SET NULL,
          status TEXT NOT NULL DEFAULT 'new',
          relevance_reason TEXT NULL,
          created_at TEXT NOT NULL,
          CHECK (status IN ('new', 'saved', 'ignored'))
        );

        CREATE TABLE IF NOT EXISTS alert_settings (
          id TEXT PRIMARY KEY,
          user_id TEXT NULL UNIQUE,
          new_paper INTEGER NOT NULL DEFAULT 1,
          new_version INTEGER NOT NULL DEFAULT 1,
          new_citation INTEGER NOT NULL DEFAULT 0,
          digest_enabled INTEGER NOT NULL DEFAULT 1,
          digest_frequency TEXT NOT NULL DEFAULT 'weekly',
          updated_at TEXT NOT NULL,
          CHECK (digest_frequency IN ('daily', 'weekly', 'off'))
        );

        CREATE TABLE IF NOT EXISTS user_model_settings (
          id TEXT PRIMARY KEY,
          user_id TEXT NULL UNIQUE,
          llm_provider TEXT NOT NULL DEFAULT 'deepseek',
          llm_model TEXT NULL,
          llm_api_key TEXT NULL,
          llm_base_url TEXT NULL,
          embedding_provider TEXT NOT NULL DEFAULT 'siliconflow',
          embedding_model TEXT NULL,
          embedding_api_key TEXT NULL,
          embedding_base_url TEXT NULL,
          embedding_dim INTEGER NULL,
          rerank_provider TEXT NOT NULL DEFAULT 'siliconflow',
          rerank_model TEXT NULL,
          rerank_api_key TEXT NULL,
          rerank_base_url TEXT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
          id TEXT PRIMARY KEY,
          user_id TEXT NULL,
          kind TEXT NOT NULL,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'unread',
          created_at TEXT NOT NULL,
          delivered_at TEXT NULL,
          CHECK (status IN ('unread', 'read', 'delivered'))
        );

        CREATE TABLE IF NOT EXISTS reading_log (
          id TEXT PRIMARY KEY,
          user_id TEXT NULL,
          paper_id TEXT NOT NULL,
          day TEXT NOT NULL,
          seconds INTEGER NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS weekly_reports (
          user_id TEXT NOT NULL,
          week_start TEXT NOT NULL,
          content TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (user_id, week_start)
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reading_log_user_day ON reading_log(user_id, day)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reading_log_paper ON reading_log(paper_id, day)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_user_status ON papers(user_id, reading_status, updated_at DESC)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_user_doi ON papers(user_id, doi) WHERE doi IS NOT NULL")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_user_arxiv ON papers(user_id, arxiv_id) WHERE arxiv_id IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_paper_id ON sessions(paper_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_session_id ON documents(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_paper_id ON documents(paper_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash) WHERE file_hash IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_session_id ON chunks(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_unique_document_chunk ON chunks(document_id, chunk_index)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_paper_id ON chunks(paper_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_steps_run_step "
        "ON agent_steps(run_id, step_index)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_session "
        "ON agent_runs(session_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_client_message "
        "ON agent_runs(client_message_id) WHERE client_message_id IS NOT NULL"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_session_status ON jobs(session_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_paper_id ON jobs(paper_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_index_snapshots_session_status ON index_snapshots(session_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_list ON sessions(is_archived, is_pinned, updated_at DESC) WHERE is_archived = 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_annotations_paper ON annotations(paper_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_annotations_chunk ON annotations(chunk_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_papers_paper ON collection_papers(paper_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_paper_tags_tag ON paper_tags(tag)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_user_kind_value ON subscriptions(user_id, kind, value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_active ON subscriptions(user_id, is_active, created_at)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_feed_items_user_source_external ON feed_items(user_id, source, external_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feed_items_user_status ON feed_items(user_id, status, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_status ON notifications(user_id, status, created_at DESC)")
