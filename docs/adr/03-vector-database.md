# ADR 03: Vector Database Selection

| Status   | accepted                       |
| -------- | ------------------------------ |
| Author   | @freinold                      |
| Voters   | @l0renor, @lenabMUC, @freinold |
| Drafted  | 2025-11-07                     |
| Accepted | 2025-11-10                     |

## Context and Problem Statement

Vector databases are specialized systems designed to efficiently store, index, and search high-dimensional vector representations of data, such as text embeddings.
They are essential for semantic search and retrieval-augmented generation (RAG) scenarios, where finding similar documents or context based on vector similarity is required.

For our use case, the vector database must meet the following criteria:

- Lightweight and easy to operate
- Support storing documents or metadata alongside vectors
- Enable flexible and efficient filtering of stored data
- Integrate smoothly with frameworks like LangChain

## Considered Options

- Qdrant
- pgVector (Postgres extension)

## Evaluation

### Qdrant

- **Slim footprint**: Qdrant is a standalone, lightweight service with minimal dependencies.
- **Good document support**: Supports storing payloads (documents/metadata) alongside vectors.
- **Easy filtering**: Advanced filtering capabilities on payloads.
- **LangChain integration**: Official integration and good community support.

### pgVector

- **Slim footprint**: Requires running a full Postgres instance; heavier than Qdrant.
- **Good document support**: Can store documents in tables, but less optimized for vector+payload use cases.
- **Easy filtering**: Leverages SQL for filtering, but may require more complex queries.
- **LangChain integration**: Supported, but less feature-rich than Qdrant integration.

## Overview

| Criterion             | Qdrant | pgVector |
| --------------------- | ------ | -------- |
| Slim footprint        | ++     | -        |
| Document support      | ++     | +        |
| Easy filtering        | ++     | +        |
| LangChain integration | ++     | +        |

## Decision Made

We choose **Qdrant** as our vector database.
It offers a slim footprint, excellent document and filtering support, and integrates seamlessly with LangChain.
While pgVector is a solid option for Postgres-centric stacks, Qdrant is better suited for our requirements.
