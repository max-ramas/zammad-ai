# zammad-ai-index

The zammad-ai-index service synchronizes content from the Zammad Knowledge Base into a Qdrant collection.
Its purpose is to provide consistent and efficient vector indexing for downstream AI-based search and response workflows.

## Purpose

zammad-ai-index performs a scheduled or manual synchronization between Zammad and Qdrant. During this process, it:

- indexes new or updated knowledge base content
- removes content from Qdrant that no longer exists in Zammad
- avoids unnecessary re-indexing through change detection

## Processing Flow

The indexing run follows a fixed, fault-tolerant workflow:

1. Determine relevant answer IDs from Zammad (full or incremental mode)
2. Retrieve the corresponding answer data
3. Transform content into the internal Qdrant document format
4. Compare against existing Qdrant points to detect changes
5. Create a Qdrant snapshot before writing
6. Write new or updated documents in batches
7. Remove obsolete Qdrant points that no longer exist in Zammad

## Prerequisites

- Python 3.13
- uv as dependency and execution tool
- reachable Qdrant server
- valid Zammad credentials

## Setup

1. Change to the project directory.

```bash
cd zammad-ai-index
```

2. Install dependencies.

```bash
uv sync
```

3. Create the configuration file.

```bash
cp config.example.yaml config.yaml
```

4. Configure values in config.yaml.

At minimum, configure:

- Zammad connection settings
- Qdrant connection settings
- index parameters such as batch size

## Run

```bash
uv run main.py
```

## Runtime Behavior

- The run exits without writing if no new or updated documents are detected.
- If snapshot creation fails, the run is aborted before any update is written.
- Connections to Zammad and Qdrant are closed in a controlled way at the end of the run.
