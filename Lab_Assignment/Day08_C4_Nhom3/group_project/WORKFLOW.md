# Workflow RAG Chatbot

## Phuong an chon

San pham: FastAPI + Next.js RAG Chatbot cho phap luat ma tuy va tin tuc nghe si lien quan den ma tuy.

Ly do chon:
- Gan san pham that hon Streamlit: frontend va backend tach rieng.
- De demo local: co the chay `docker compose up --build`.
- Phu hop tieng Viet: `BAAI/bge-m3` cho multilingual embedding, lexical BM25, reranker multilingual.
- On dinh khi thieu dich vu ngoai: co fallback local neu chua bat Elasticsearch, chua co OpenAI key, hoac chua cache model Qwen/BGE.
- Co citation: cau tra loi hien nguon va context truy xuat.

## Kien truc

```text
data/landing/
  -> task3_convert_markdown.py
  -> data/standardized/
  -> task4_chunking_indexing.py
  -> data/indexes/chunks.json
  -> FastAPI backend
      -> Supervisor - Workers
          -> Query Planner Worker
          -> Retrieval Worker
              -> task5 semantic search
              -> task6 Elasticsearch BM25/local BM25 search
              -> task7 reranking
              -> task9 hybrid retrieval
          -> Answer Worker
              -> task10 generation with citation
  -> Next.js frontend
```

Trong luc chat, nguon du lieu runtime duy nhat la `data/indexes/chunks.json`.
Pipeline khong crawl lai va khong doc raw landing files. Cac file landing va
standardized chi dung de tao index o Task 3/Task 4.

## Cong nghe

| Thanh phan | Lua chon | Ghi chu |
|------------|----------|---------|
| UI | Next.js | Chat UI tach rieng backend, de demo nhu web app that |
| API | FastAPI | API ro rang cho chat/search/stats/rebuild |
| Orchestration | Supervisor - Workers | Supervisor dieu phoi 3 worker: query planner, retrieval, answer |
| Chunking | SemanticChunker | Tach theo cum ngu nghia, tot hon cat ky tu thuan |
| Embedding | BAAI/bge-m3 | Multilingual, phu hop tieng Viet |
| Lexical | Elasticsearch BM25 | Tot cho query co dieu/khoan/tu khoa phap ly |
| Reranking | Qwen3-Reranker | Multilingual reranker, phu hop cau hoi tieng Viet |
| Generation | OpenAI optional | Neu thieu key thi fallback extractive co citation |

## Cach chay

```bash
pip install -r requirements.txt
python src/task3_convert_markdown.py
python src/task4_chunking_indexing.py
uvicorn backend.app.main:app --reload --port 8000
cd frontend
npm install
npm run dev
```

Chay bang Docker:

```bash
docker compose up --build
```

## Che do nang cao

Neu da tai model ve local:

```bash
USE_REAL_BGE_M3=1 USE_QWEN_RERANKER=1 python src/task4_chunking_indexing.py
USE_REAL_BGE_M3=1 USE_QWEN_RERANKER=1 uvicorn backend.app.main:app --reload --port 8000
```

Neu co Elasticsearch:

```bash
export ELASTICSEARCH_URL=http://localhost:9200
uvicorn backend.app.main:app --reload --port 8000
```

Neu co OpenAI key:

```bash
export OPENAI_API_KEY=...
uvicorn backend.app.main:app --reload --port 8000
```

## Checklist hoan thien bao cao

- Mo ta data dau vao: 4 van ban phap luat, 7 bai VnExpress.
- Mo ta pipeline: semantic chunking, embedding, lexical, rerank, generation.
- Demo cau hoi phap luat: cai nghien, tang tru, su dung trai phep.
- Demo cau hoi tin tuc: nghe si lien quan den ma tuy trong data.
- Chay evaluation: `python group_project/evaluation/eval_pipeline.py`.
- Bo sung golden dataset len 15 cau neu can nop phan evaluation day du.
