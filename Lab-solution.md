Nguyễn Công Thành - 2A202600696
# Lab Solution Report - Multi-Agent, MCP and A2A

## 1. Tong quan

Project nay duoc hoan thien theo noi dung trong `CODELAB.md`, bao gom cac bai tap co ban va phan nang cao ve:

- Goi LLM truc tiep.
- Ket hop RAG va tools.
- Xay dung single agent theo kieu ReAct.
- Xay dung multi-agent trong cung mot chuong trinh.
- Dieu phoi cac agent phan tan thong qua A2A.

Muc tieu chinh cua project la minh hoa cach mot he thong legal assistant co the phat trien tu mot LLM don gian thanh mot pipeline co truy xuat du lieu, goi cong cu, phan cong tac vu cho nhieu agent chuyen mon va trao doi giua cac service rieng biet bang giao thuc A2A.

## 2. Cau hinh moi truong va LLM

Project su dung OpenRouter lam cong ket noi den LLM. De phu hop voi yeu cau chay mien phi, cau hinh da duoc dieu chinh theo huong:

- `OPENROUTER_MODEL=openrouter/free`
- `OPENROUTER_FORCE_FREE=true`
- `OPENROUTER_MAX_TOKENS=4096`
- `OPENROUTER_TIMEOUT_SECONDS=60`

Trong `.env.example`, API key duoc de dang placeholder de tranh lo khoa that. File `.env` local chua API key rieng cua nguoi chay, khong nen commit len git.

Phan common LLM da duoc bo sung co che an toan hon:

- Neu thieu API key hoac API key con la placeholder, chuong trinh khong crash ma dung local fallback.
- Neu OpenRouter bi loi het credit, model khong kha dung, timeout hoac loi ket noi, chuong trinh van co cau tra loi fallback de pipeline tiep tuc chay.
- Co cau hinh `max_tokens` lon hon de phu hop voi du lieu va cau tra loi dai.
- Co xu ly normalize tool-call name de giam loi khi model free tra ve ten tool khong dung dinh dang.

## 3. Cac bai da hoan thanh

### Stage 1 - Direct LLM Calling

Stage 1 minh hoa cach goi LLM truc tiep bang system prompt va user question.

Da hoan thien:

- Khoi tao LLM dung cau hinh OpenRouter.
- Chay duoc voi model `openrouter/free`.
- Co fallback khi thieu key hoac OpenRouter bi loi.
- Giu dung input/output cua bai: in phan mo ta cach hoat dong, cau hoi, cau tra loi va gioi han cua direct LLM.

Y nghia:

- Stage nay cho thay LLM co the tra loi nhanh nhung khong co grounding.
- Khong co tool, khong co truy xuat tai lieu, khong co bo nho hoi thoai.

Lenh chay:

```bash
uv run python stages/stage_1_direct_llm/main.py
```

### Stage 2 - RAG and Tools

Stage 2 bo sung tri thuc va cong cu de cau tra loi co can cu hon.

Da hoan thien:

- Them knowledge base cho labor law.
- Bo sung tool `check_statute_of_limitations`.
- Giu cac tool phap ly da co va mo rong them kha nang tra cuu.
- Dieu chinh tool invocation theo cach on dinh hon de tranh treo khi goi async/thread trong mot so moi truong.

Y nghia:

- LLM khong chi dua vao kien thuc huan luyen.
- Cau tra loi co the dua vao du lieu noi bo va cong cu tinh/kiem tra.
- Day la buoc chuyen tu "hoi LLM" sang "hoi he thong co tri thuc va hanh dong".

Lenh chay:

```bash
uv run python stages/stage_2_rag_tools/main.py
```

### Stage 3 - Single Agent with ReAct

Stage 3 xay dung mot agent co kha nang suy nghi, chon tool va tong hop ket qua.

Da hoan thien:

- Bo sung tool `search_case_law`.
- Agent co the chon dung tool dua tren cau hoi.
- Co phan in step, tool call va ket qua de de quan sat qua trinh agent lam viec.
- Debug LangGraph duoc dieu khien bang bien moi truong `LANGGRAPH_DEBUG`.
- Them co che normalize tool name khi model free tra ve ten tool loi dinh dang.

Y nghia:

- Agent khong chi tra loi mot lan ma co vong lap: doc cau hoi, quyet dinh can tool nao, goi tool, doc ket qua, roi tong hop.
- Phu hop voi bai toan phap ly vi can lay thong tin tu nhieu nguon truoc khi tra loi.

Lenh chay:

```bash
uv run python stages/stage_3_single_agent/main.py
```

### Stage 4 - Multi-Agent trong cung chuong trinh

Stage 4 mo rong tu single agent sang nhieu agent chuyen mon.

Da hoan thien:

- `law_agent`: phan tich phap ly tong quan va dieu phoi.
- `tax_agent`: xu ly van de thue.
- `compliance_agent`: xu ly van de tuan thu.
- `privacy_agent`: xu ly van de rieng tu va bao ve du lieu.
- `financial_agent`: phan nang cao, ho tro phan tich khia canh tai chinh khi can.
- Co routing de quyet dinh can goi agent nao dua tren noi dung cau hoi.
- Co aggregation de tong hop ket qua tu cac specialist thanh cau tra loi cuoi.
- Co fallback va xu ly loi khi LLM tra ve rong hoac API bi loi.
- Co bo nho hoi thoai don gian de giu ngu canh.

Pipeline Stage 4:

```text
User question
    -> law_agent phan tich ban dau
    -> router xac dinh specialist can goi
    -> tax/compliance/privacy/financial agent xu ly phan viec
    -> aggregate_results tong hop
    -> final answer
```

Y nghia:

- Moi agent co vai tro ro rang, giup cau tra loi co cau truc va day du hon.
- Multi-agent phu hop khi cau hoi co nhieu khia canh: legal, tax, compliance, privacy, financial.
- Viec tong hop o cuoi rat quan trong de tranh tra loi bi roi rac.

Lenh chay:

```bash
uv run python stages/stage_4_milti_agent/main.py
```

### Stage 5 - A2A Distributed Agents

Stage 5 tach cac agent thanh nhieu service rieng va giao tiep qua A2A.

Da hoan thien:

- `registry_server`: luu va cung cap thong tin agent.
- `customer_agent`: diem vao cho client, nhan cau hoi tu nguoi dung.
- `law_agent`: agent dieu phoi chinh cho bai toan legal.
- `tax_agent`: specialist ve thue.
- `compliance_agent`: specialist ve tuan thu.
- `common/a2a_client.py`: client goi agent khac qua A2A, co retry.
- `common/registry_client.py`: client tra cuu registry, co retry.
- `start_all.sh`: khoi dong toan bo service bang `uv run python -m ...`.
- `test_client.py`: kiem thu pipeline tu dau den cuoi.

Pipeline A2A:

```text
test_client.py / User
    -> customer_agent
    -> registry_server de tim law_agent
    -> law_agent nhan task va phan tich cau hoi
    -> law_agent quyet dinh co can specialist hay khong
    -> registry_server de tim tax_agent/compliance_agent
    -> tax_agent va compliance_agent xu ly phan viec
    -> law_agent tong hop artifact tu specialists
    -> customer_agent nhan ket qua
    -> client nhan final response
```

Trong A2A, cac agent trao doi thong qua task/message/artifact thay vi goi ham truc tiep. Cach nay mo phong gan hon mot he thong that, trong do moi agent co the la mot service doc lap, chay cong rieng va co the duoc thay the/mo rong rieng.

Lenh chay:

```bash
./start_all.sh
uv run python test_client.py
```

## 4. Dieu phoi agent

Trong project, viec dieu phoi agent duoc thuc hien theo hai cach.

### Multi-agent local

O Stage 4, cac agent nam trong cung mot graph. Router dieu huong luong xu ly dua tren noi dung cau hoi.

Vi du:

- Cau hoi ve thue se goi `tax_agent`.
- Cau hoi ve quy dinh/tuan thu se goi `compliance_agent`.
- Cau hoi ve du lieu ca nhan, privacy, GDPR se goi `privacy_agent`.
- Cau hoi co yeu to tai chinh se co the goi `financial_agent`.

Uu diem:

- Nhanh hon vi khong can giao tiep qua network.
- De debug hon vi toan bo state nam trong mot chuong trinh.
- Phu hop de hoc va thu nghiem pipeline.

Han che:

- Kho tach service doc lap.
- Khi so agent tang, graph va state de phuc tap.
- Khong mo phong day du moi truong phan tan.

### A2A distributed agents

O Stage 5, moi agent la mot service rieng. `registry_server` dong vai tro nhu danh ba. Agent nao can goi specialist thi hoi registry truoc, sau do gui task qua A2A.

Vai tro chinh:

- `customer_agent`: nhan request tu client va tra response cuoi.
- `law_agent`: dieu phoi nghiep vu phap ly va tong hop cau tra loi.
- `tax_agent`: xu ly phan thue.
- `compliance_agent`: xu ly phan tuan thu.
- `registry_server`: dang ky va phat hien agent.

De tang do on dinh, project da co:

- Retry khi goi A2A.
- Retry khi discover agent tu registry.
- Trace/context/depth de theo doi va han che vong goi long nhau.
- Fallback khi LLM hoac service gap loi.

## 5. Nhan xet ve Multi-Agent

Multi-agent giup chia bai toan lon thanh nhieu phan nho theo chuyen mon. Voi bai toan legal assistant, day la cach thiet ke hop ly vi mot cau hoi phap ly co the lien quan den hop dong, thue, tuan thu, rieng tu du lieu va rui ro tai chinh.

Diem manh:

- Moi agent co prompt, tool va trach nhiem rieng.
- De mo rong them specialist moi.
- Cau tra loi day du hon khi cau hoi co nhieu khia canh.
- Co the chay song song mot so nhanh xu ly.

Diem can chu y:

- Can routing tot, neu khong agent se bi goi thua hoac thieu.
- Can aggregator tot de cau tra loi cuoi khong bi lap va khong mau thuan.
- Can quan ly state ro rang.
- Can xu ly loi vi chi can mot specialist loi la pipeline co the anh huong.

## 6. Nhan xet ve A2A

A2A phu hop khi cac agent can chay doc lap va giao tiep nhu cac service rieng. So voi multi-agent local, A2A gan voi kien truc production hon.

Diem manh:

- Loose coupling: moi agent co the phat trien va deploy rieng.
- Registry giup discovery linh hoat, khong can hard-code tat ca endpoint.
- De them agent moi vao he thong neu tuan theo cung protocol.
- Phu hop voi bai toan co nhieu nhom phu trach cac agent khac nhau.

Diem can chu y:

- Debug kho hon vi loi co the nam o client, registry, agent dich hoac network.
- Can retry, timeout va fallback.
- Can trace id/context id de theo doi mot request qua nhieu service.
- Can guard de tranh vong lap goi agent qua lai qua sau.
- Latency cao hon local graph vi co giao tiep HTTP giua service.

Ket luan ngan gon: multi-agent local phu hop de thiet ke logic va thu nghiem nhanh; A2A phu hop khi muon dua he thong sang dang phan tan, mo rong duoc va gan voi thuc te trien khai.

## 7. Kiem thu

Project da duoc chuan bi de chay cac lenh kiem thu sau:

```bash
uv run python stages/stage_1_direct_llm/main.py
uv run python stages/stage_2_rag_tools/main.py
uv run python stages/stage_3_single_agent/main.py
uv run python stages/stage_4_milti_agent/main.py
./start_all.sh
uv run python test_client.py
```

Ket qua mong doi:

- Stage 1 tra loi truc tiep tu LLM hoac fallback neu OpenRouter loi.
- Stage 2 co goi knowledge/tools.
- Stage 3 co qua trinh agent chon tool va tong hop.
- Stage 4 co dieu phoi nhieu specialist trong mot graph.
- Stage 5 va `test_client.py` kiem tra duoc pipeline A2A end-to-end.

Luu y khi chay:

- Neu thay canh bao `VIRTUAL_ENV does not match the project environment path .venv`, day la canh bao cua `uv`, khong phai loi logic cua project. Co the `deactivate` moi truong cu roi chay lai.
- Neu OpenRouter free model khong on dinh, pipeline van co fallback de tranh crash.
- Khong commit API key that trong `.env`.

## 8. Ket luan

Project da hoan thien day du cac phan chinh cua bai lab va phan nang cao. He thong bat dau tu direct LLM, sau do them RAG/tools, single agent, multi-agent local va cuoi cung la A2A distributed agents.

Diem quan trong nhat cua project la pipeline da the hien duoc cach dieu phoi nhieu agent theo vai tro: agent dau vao nhan yeu cau, agent phap ly dieu phoi, cac specialist xu ly phan viec va aggregator tong hop cau tra loi cuoi. Thiet ke nay giup he thong de mo rong, de them chuyen mon moi va gan voi cach xay dung ung dung agentic trong thuc te.
