# Tasks: Embedding Layer

**Feature Branch**: `016-embedding-layer`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Add pgvector and openai to `backend/requirements/base.txt`
- [x] T002 Create AI domain at `backend/src/domain/ai/` with ports
- [x] T003 Create embedding infrastructure at `backend/src/infrastructure/ai/`

## Phase 2: EmbeddingProviderPort

- [x] T004 Create EmbeddingProviderPort abstract class at `backend/src/domain/ai/ports/embedding_provider_port.py`
- [x] T005 Define embed_text method signature
- [x] T006 Define batch_embed_texts method
- [x] T007 Create EmbeddingResult dataclass

## Phase 3: [US1] OpenAI Embeddings Provider

- [x] T008 [US1] Create OpenAIEmbeddingAdapter at `backend/src/infrastructure/ai/openai_embeddings.py`
- [x] T009 [US1] Implement text-embedding-3-small integration
- [x] T010 [US1] Support batch embedding requests
- [x] T011 [US1] Handle API rate limits with retry logic
- [x] T012 [US1] Track embedding costs (cost_micros calculation)

## Phase 4: [US2] Local Embeddings Provider

- [ ] T013 [US2] Create SentenceTransformerProvider (deferred - using OpenAI only)
- [ ] T014 [US2] Load multilingual model (deferred)
- [ ] T015 [US2] Implement local embedding generation (deferred)
- [ ] T016 [US2] Cache model in memory (deferred)

## Phase 5: [US3] Product Embeddings

- [x] T017 [US3] Generate embeddings for product descriptions via canonical text
- [x] T018 [US3] Store embeddings in product_embedding table with pgvector
- [x] T019 [US3] Create background job `embed_product` worker with Celery
- [x] T020 [US3] Re-embed on product updates (text_hash deduplication)

## Phase 6: Polish

- [x] T021 Add embedding dimension configuration to .env.example
- [x] T022 Implement embedding caching via text_hash deduplication
- [x] T023 Add embedding quality metrics (get_embedding_stats service)
- [x] T024 Document provider selection strategy (OpenAI default, port-based architecture)
