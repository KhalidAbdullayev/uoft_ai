import json
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import faiss


with open("utm.json", encoding="utf8") as f:
    pages = json.load(f)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = []
    for page in pages:
        pieces = splitter.split_text(page["text"])
        for piece in pieces:
            chunks.append({"url": page["url"], "text": piece})

# tokenizer = AutoTokenizer.from_pretrained(
#     "Qwen/Qwen2.5-3B-Instruct"
# )
#
# llm = AutoModelForCausalLM.from_pretrained(
#     "Qwen/Qwen2.5-3B-Instruct", torch_dtype=torch.float32)

embedding_model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)

embeddings = embedding_model.encode(
    [chunk["text"] for chunk in chunks],
    normalize_embeddings=True,
    convert_to_numpy=True
)

index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings.astype("float32"))
faiss.write_index(index, "utm.index")
with open("chunks.json", "w", encoding="utf8") as f:
    # noinspection PyTypeChecker
    json.dump(chunks, f, ensure_ascii=False, indent=4)