import threading

from backend.storage.sqlite.connection import connect

CURRENT_SCHEMA_VERSION = 10

_init_lock = threading.RLock()


def init_db() -> None:
    """Thread-safe schema initialization and migration."""
    with _init_lock:
        conn = connect()
        try:
            current_version = conn.execute("PRAGMA user_version").fetchone()[0]
            if current_version < 1:
                # Fresh database: the initial schema already matches the current
                # version, so no incremental migration must run on top of it.
                _create_initial_schema(conn)
                conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            elif current_version < CURRENT_SCHEMA_VERSION:
                _migrate_schema(conn, current_version)
                conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _migrate_schema(conn, from_version: int) -> None:
    """Run incremental schema migrations."""
    if from_version < 2:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_unique_document_chunk "
            "ON chunks(document_id, chunk_index)"
        )
    if from_version < 3:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(retrieval_indexes)")}
        if "created_at" not in columns:
            conn.execute("ALTER TABLE retrieval_indexes ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
            conn.execute("UPDATE retrieval_indexes SET created_at = updated_at WHERE created_at = ''")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_list "
            "ON sessions(is_archived, is_pinned, updated_at DESC) WHERE is_archived = 0"
        )
    if from_version < 4:
        _migrate_add_cascade_delete(conn)
    if from_version < 5:
        _migrate_add_users_table(conn)
    if from_version < 6:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        if "client_message_id" not in columns:
            conn.execute("ALTER TABLE messages ADD COLUMN client_message_id TEXT NULL")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_client_id "
            "ON messages(client_message_id) WHERE client_message_id IS NOT NULL"
        )
    if from_version < 7:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        for column, ddl_type in (
            ("model", "TEXT"),
            ("prompt_tokens", "INTEGER"),
            ("completion_tokens", "INTEGER"),
        ):
            if column not in columns:
                conn.execute(f"ALTER TABLE messages ADD COLUMN {column} {ddl_type} NULL")
    if from_version < 8:
        _migrate_add_papers(conn)
    if from_version < 9:
        _migrate_add_feed(conn)
    if from_version < 10:
        _migrate_add_alert_settings(conn)


def _migrate_add_users_table(conn) -> None:
    """Add users table for JWT auth (v5)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            hashed_password TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)


def _migrate_add_cascade_delete(conn) -> None:
    """Recreate FK-bearing tables with ON DELETE CASCADE (v4)."""
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript("""
        CREATE TABLE documents_new (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          filename TEXT NOT NULL,
          file_path TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          file_size INTEGER NOT NULL,
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
        INSERT INTO documents_new SELECT * FROM documents;
        DROP TABLE documents;
        ALTER TABLE documents_new RENAME TO documents;

        CREATE TABLE messages_new (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          sources_json TEXT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        INSERT INTO messages_new SELECT * FROM messages;
        DROP TABLE messages;
        ALTER TABLE messages_new RENAME TO messages;

        CREATE TABLE chunks_new (
          id TEXT PRIMARY KEY,
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
        INSERT INTO chunks_new SELECT * FROM chunks;
        DROP TABLE chunks;
        ALTER TABLE chunks_new RENAME TO chunks;

        CREATE TABLE retrieval_indexes_new (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          index_path TEXT NOT NULL,
          chunks_path TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        INSERT INTO retrieval_indexes_new SELECT * FROM retrieval_indexes;
        DROP TABLE retrieval_indexes;
        ALTER TABLE retrieval_indexes_new RENAME TO retrieval_indexes;

        CREATE TABLE jobs_new (
          id TEXT PRIMARY KEY,
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
        INSERT INTO jobs_new SELECT * FROM jobs;
        DROP TABLE jobs;
        ALTER TABLE jobs_new RENAME TO jobs;

        CREATE TABLE index_snapshots_new (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          status TEXT NOT NULL,
          index_path TEXT NOT NULL,
          chunks_path TEXT NOT NULL,
          document_ids_json TEXT NOT NULL,
          error_message TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        INSERT INTO index_snapshots_new SELECT * FROM index_snapshots;
        DROP TABLE index_snapshots;
        ALTER TABLE index_snapshots_new RENAME TO index_snapshots;
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_session_id ON documents(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_session_id ON chunks(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_unique_document_chunk ON chunks(document_id, chunk_index)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_session_status ON jobs(session_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_index_snapshots_session_status ON index_snapshots(session_id, status)")
    conn.execute("PRAGMA foreign_keys = ON")



def _migrate_add_papers(conn) -> None:
    """Add papers, reading state, annotations and link existing rows (v8)."""
    # PRAGMA foreign_keys is a no-op inside a transaction.
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        BEGIN IMMEDIATE;
        DROP TABLE IF EXISTS documents_new;
        DROP TABLE IF EXISTS chunks_new;
        DROP TABLE IF EXISTS jobs_new;

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

        ALTER TABLE sessions ADD COLUMN paper_id TEXT NULL REFERENCES papers(id) ON DELETE SET NULL;

        INSERT INTO papers (
          id, user_id, title, reading_status, progress, last_location_json,
          last_read_at, time_spent_seconds, created_at, updated_at
        )
        SELECT
          'paper_' || d.id,
          u.id,
          CASE WHEN d.filename LIKE '%.pdf'
               THEN substr(d.filename, 1, length(d.filename) - 4)
               ELSE d.filename END,
          'inbox', 0, NULL, NULL, 0, d.created_at, d.updated_at
        FROM documents d
        JOIN sessions s ON s.id = d.session_id
        LEFT JOIN users u ON u.id = s.user_id;

        CREATE TABLE documents_new (
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
        INSERT INTO documents_new (
          id, paper_id, session_id, filename, file_path, mime_type, file_size,
          file_hash, chunk_count, status, error_message, created_at, updated_at,
          parsed_ir_path, parsed_markdown_path, quality_report_path, parser_name,
          parser_version, parse_quality_status
        )
        SELECT
          id, 'paper_' || id, session_id, filename, file_path, mime_type, file_size,
          NULL, chunk_count, status, error_message, created_at, updated_at,
          parsed_ir_path, parsed_markdown_path, quality_report_path, parser_name,
          parser_version, parse_quality_status
        FROM documents;
        DROP TABLE documents;
        ALTER TABLE documents_new RENAME TO documents;

        CREATE TABLE chunks_new (
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
        INSERT INTO chunks_new (
          id, paper_id, session_id, document_id, section, chunk_index,
          text_excerpt, text_content, type, created_at, section_path_json,
          page_start, page_end, bbox_json, block_ids_json, block_types_json,
          linked_block_ids_json, confidence
        )
        SELECT
          id, 'paper_' || document_id, session_id, document_id, section, chunk_index,
          text_excerpt, text_content, type, created_at, section_path_json,
          page_start, page_end, bbox_json, block_ids_json, block_types_json,
          linked_block_ids_json, confidence
        FROM chunks;
        DROP TABLE chunks;
        ALTER TABLE chunks_new RENAME TO chunks;

        CREATE TABLE jobs_new (
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
        INSERT INTO jobs_new (
          id, paper_id, session_id, document_id, type, status, stage, attempt,
          error_message, payload_json, created_at, started_at, finished_at
        )
        SELECT
          id,
          CASE WHEN document_id IS NOT NULL THEN 'paper_' || document_id ELSE NULL END,
          session_id, document_id, type, status, stage, attempt,
          error_message, payload_json, created_at, started_at, finished_at
        FROM jobs;
        DROP TABLE jobs;
        ALTER TABLE jobs_new RENAME TO jobs;

        CREATE TABLE annotations (
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

        UPDATE sessions
        SET paper_id = (
          SELECT 'paper_' || d.id FROM documents d
          WHERE d.session_id = sessions.id
          ORDER BY d.created_at ASC
          LIMIT 1
        );

        CREATE INDEX IF NOT EXISTS idx_papers_user_status
          ON papers(user_id, reading_status, updated_at DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_user_doi
          ON papers(user_id, doi) WHERE doi IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_user_arxiv
          ON papers(user_id, arxiv_id) WHERE arxiv_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_sessions_paper_id ON sessions(paper_id);
        CREATE INDEX IF NOT EXISTS idx_documents_session_id ON documents(session_id);
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
        CREATE INDEX IF NOT EXISTS idx_documents_paper_id ON documents(paper_id);
        CREATE INDEX IF NOT EXISTS idx_documents_file_hash
          ON documents(file_hash) WHERE file_hash IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_chunks_session_id ON chunks(session_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_unique_document_chunk
          ON chunks(document_id, chunk_index);
        CREATE INDEX IF NOT EXISTS idx_chunks_paper_id ON chunks(paper_id);
        CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_session_status ON jobs(session_id, status);
        CREATE INDEX IF NOT EXISTS idx_jobs_paper_id ON jobs(paper_id);
        CREATE INDEX IF NOT EXISTS idx_index_snapshots_session_status
          ON index_snapshots(session_id, status);
        CREATE INDEX IF NOT EXISTS idx_sessions_list
          ON sessions(is_archived, is_pinned, updated_at DESC)
          WHERE is_archived = 0;
        CREATE INDEX IF NOT EXISTS idx_annotations_paper
          ON annotations(paper_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_annotations_chunk ON annotations(chunk_id);
        CREATE INDEX IF NOT EXISTS idx_collection_papers_paper ON collection_papers(paper_id);
        CREATE INDEX IF NOT EXISTS idx_paper_tags_tag ON paper_tags(tag);
        COMMIT;
        """
    )
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"schema v8 foreign key check failed: {violations}")



def _migrate_add_feed(conn) -> None:
    """Add subscriptions and feed items (v9)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
          id TEXT PRIMARY KEY,
          user_id TEXT NULL,
          kind TEXT NOT NULL,
          value TEXT NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          last_checked_at TEXT NULL,
          CHECK (kind IN ('keyword', 'author', 'venue', 'institution'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_user_kind_value
          ON subscriptions(user_id, kind, value);
        CREATE INDEX IF NOT EXISTS idx_subscriptions_user_active
          ON subscriptions(user_id, is_active, created_at);

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
        CREATE UNIQUE INDEX IF NOT EXISTS idx_feed_items_user_source_external
          ON feed_items(user_id, source, external_id);
        CREATE INDEX IF NOT EXISTS idx_feed_items_user_status
          ON feed_items(user_id, status, created_at DESC);
        """
    )


def _migrate_add_alert_settings(conn) -> None:
    """Add local alert/digest preferences (v10)."""
    conn.executescript(
        """
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
        """
    )


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
        """
    )
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
