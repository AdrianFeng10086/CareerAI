"""
职业规划岗位向量存储服务。

设计目标:
1. 以向量数据库存储岗位信息，支持高效的语义检索和相似度计算。
2. 提供语义检索能力，支持 RAG 上下文拼装。
3. 优先使用 GPU 进行向量嵌入，无 GPU 时自动回退 CPU。
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import math
import os
import re
import threading
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List

VECTOR_DB_DIR = "career_jobs_vector_db"
COLLECTION_NAME = "jobs"
_DEFAULT_HF_MIRROR = "https://hf-mirror.com"
_HUGGING_FACE_ENDPOINTS = {
    "https://huggingface.co",
    "https://www.huggingface.co",
}

_DB_LOCK = threading.Lock()
_EMBEDDER_LOCK = threading.Lock()


def _canonical_endpoint(value: str, default_value: str = "") -> str:
    endpoint = str(value or "").strip()
    if not endpoint:
        endpoint = str(default_value or "").strip()
    if not endpoint:
        return ""
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"https://{endpoint}"
    return endpoint.rstrip("/")


def _is_huggingface_endpoint(value: str) -> bool:
    return _canonical_endpoint(value).lower() in _HUGGING_FACE_ENDPOINTS


def _resolve_embed_hf_endpoint() -> str:
    endpoint = _canonical_endpoint(
        os.getenv("CAREER_RAG_HF_ENDPOINT", _DEFAULT_HF_MIRROR),
        default_value=_DEFAULT_HF_MIRROR,
    )
    if _is_huggingface_endpoint(endpoint):
        return _DEFAULT_HF_MIRROR
    return endpoint


def _apply_hf_endpoint_env() -> str:
    preferred = _resolve_embed_hf_endpoint()
    current = _canonical_endpoint(os.getenv("HF_ENDPOINT", ""))
    if not current or _is_huggingface_endpoint(current):
        os.environ["HF_ENDPOINT"] = preferred
        return preferred
    return current

_EMBED_MODEL_NAME = str(
    os.getenv("CAREER_RAG_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
).strip()
_EMBED_HF_ENDPOINT = _resolve_embed_hf_endpoint()
_EMBEDDER: Any = None
_EMBEDDER_READY = False
_EMBEDDER_DEVICE = "cpu"
_EMBEDDER_DTYPE = "float32"
_EMBEDDER_BACKEND = "hash-fallback"
_EMBEDDER_ERROR = ""
_TORCH_MODULE: Any = None

_VECTOR_DIM = 384
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_+.#-]+|[\u4e00-\u9fff]")


def _load_chromadb() -> Any:
    try:
        chromadb = importlib.import_module("chromadb")
    except Exception as exc:
        raise RuntimeError("缺少 chromadb 依赖，请先执行 pip install -r requirements.txt") from exc
    return chromadb


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "1" if default else "0") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _get_torch_module() -> Any:
    global _TORCH_MODULE
    if _TORCH_MODULE is not None:
        return _TORCH_MODULE

    try:
        _TORCH_MODULE = importlib.import_module("torch")
    except Exception:
        _TORCH_MODULE = None
    return _TORCH_MODULE


def _torch_cuda_available(torch_module: Any) -> bool:
    try:
        return bool(getattr(torch_module, "cuda", None) and torch_module.cuda.is_available())
    except Exception:
        return False


def _resolve_requested_device() -> str:
    requested = str(os.getenv("CAREER_RAG_DEVICE", "cuda") or "cuda").strip().lower()
    if requested not in {"auto", "cpu", "cuda"}:
        return "cuda"
    return requested


def _resolve_gpu_dtype_flag(default: str = "float16") -> str:
    flag = str(os.getenv("CAREER_RAG_GPU_DTYPE", default) or default).strip().lower()
    if flag in {"fp16", "float16", "half"}:
        return "float16"
    if flag in {"bf16", "bfloat16"}:
        return "bfloat16"
    if flag in {"fp32", "float32"}:
        return "float32"
    return "float16"


def _resolve_torch_cuda_dtype(torch_module: Any) -> tuple[Any, str]:
    flag = _resolve_gpu_dtype_flag(default="float16")
    torch_float16 = getattr(torch_module, "float16", None)
    torch_bfloat16 = getattr(torch_module, "bfloat16", None)
    torch_float32 = getattr(torch_module, "float32", None)

    if flag == "float32":
        return (torch_float32, "float32")

    if flag == "bfloat16":
        try:
            if bool(getattr(torch_module.cuda, "is_bf16_supported", lambda: False)()):
                return (torch_bfloat16, "bfloat16")
        except Exception:
            pass
        return (torch_float16, "float16")

    return (torch_float16, "float16")


def _maybe_enable_tf32(torch_module: Any) -> bool:
    if not _env_flag("CAREER_RAG_ENABLE_TF32", default=True):
        return False

    try:
        backends = getattr(torch_module, "backends", None)
        if not backends:
            return False

        if getattr(backends, "cuda", None) and getattr(backends.cuda, "matmul", None):
            backends.cuda.matmul.allow_tf32 = True
        if getattr(backends, "cudnn", None):
            backends.cudnn.allow_tf32 = True
        return True
    except Exception:
        return False


def _is_cuda_oom_error(message: str) -> bool:
    text = str(message or "").lower()
    return any(
        marker in text
        for marker in [
            "out of memory",
            "cuda out of memory",
            "cublas_status_alloc_failed",
            "hip out of memory",
        ]
    )


def _load_sentence_transformer() -> Any:
    global _EMBEDDER
    global _EMBEDDER_READY
    global _EMBEDDER_DEVICE
    global _EMBEDDER_DTYPE
    global _EMBEDDER_BACKEND
    global _EMBEDDER_ERROR

    if _EMBEDDER_READY:
        return _EMBEDDER

    with _EMBEDDER_LOCK:
        if _EMBEDDER_READY:
            return _EMBEDDER

        try:
            torch = _get_torch_module()
            if torch is None:
                raise RuntimeError("未检测到 torch，无法启用 sentence-transformers 嵌入")

            sentence_transformers = importlib.import_module("sentence_transformers")

            requested = _resolve_requested_device()
            has_cuda = _torch_cuda_available(torch)

            if requested == "cpu":
                device = "cpu"
            elif requested == "cuda":
                device = "cuda" if has_cuda else "cpu"
            else:
                device = "cuda" if has_cuda else "cpu"

            cuda_dtype: Any = None
            cuda_dtype_name = "float32"
            if device == "cuda":
                cuda_dtype, cuda_dtype_name = _resolve_torch_cuda_dtype(torch)
                _maybe_enable_tf32(torch)

            _apply_hf_endpoint_env()
            os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
            os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
            os.environ.setdefault("TQDM_DISABLE", "1")

            local_files_only = _env_flag("CAREER_RAG_LOCAL_ONLY", default=False)
            cache_folder = str(os.getenv("CAREER_RAG_MODEL_CACHE", "") or "").strip() or None

            model_cls = getattr(sentence_transformers, "SentenceTransformer")
            model_kwargs: Dict[str, Any] = {"device": device}
            if cache_folder:
                model_kwargs["cache_folder"] = cache_folder
            if local_files_only:
                model_kwargs["local_files_only"] = True
            if device == "cuda" and cuda_dtype is not None:
                model_kwargs["model_kwargs"] = {"torch_dtype": cuda_dtype}

            try:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    _EMBEDDER = model_cls(_EMBED_MODEL_NAME, **model_kwargs)
            except TypeError:
                # 兼容旧版 sentence-transformers，可能不支持 local_files_only 参数。
                model_kwargs.pop("local_files_only", None)
                try:
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        _EMBEDDER = model_cls(_EMBED_MODEL_NAME, **model_kwargs)
                except TypeError:
                    # 兼容旧版 sentence-transformers，可能不支持 model_kwargs 参数。
                    model_kwargs.pop("model_kwargs", None)
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        _EMBEDDER = model_cls(_EMBED_MODEL_NAME, **model_kwargs)

            _EMBEDDER_DEVICE = device
            _EMBEDDER_DTYPE = cuda_dtype_name if device == "cuda" else "float32"
            _EMBEDDER_BACKEND = "sentence-transformers"
            _EMBEDDER_ERROR = ""
            if requested == "cuda" and device != "cuda":
                _EMBEDDER_ERROR = "CAREER_RAG_DEVICE=cuda 但当前 torch 未检测到可用 CUDA，已回退 CPU"
            elif requested == "cuda" and device == "cuda" and _resolve_gpu_dtype_flag(default="float16") == "bfloat16" and _EMBEDDER_DTYPE != "bfloat16":
                _EMBEDDER_ERROR = "CAREER_RAG_GPU_DTYPE=bfloat16 但当前设备不支持，已回退 float16"
        except Exception as exc:
            _EMBEDDER = None
            _EMBEDDER_DEVICE = "cpu"
            _EMBEDDER_DTYPE = "float32"
            _EMBEDDER_BACKEND = "hash-fallback"
            _EMBEDDER_ERROR = str(exc)

        _EMBEDDER_READY = True
        return _EMBEDDER


def get_embedding_runtime_info() -> Dict[str, Any]:
    if not _EMBEDDER_READY:
        _load_sentence_transformer()

    info: Dict[str, Any] = {
        "model": _EMBED_MODEL_NAME,
        "hf_endpoint": _canonical_endpoint(os.getenv("HF_ENDPOINT", _EMBED_HF_ENDPOINT), default_value=_EMBED_HF_ENDPOINT),
        "local_files_only": _env_flag("CAREER_RAG_LOCAL_ONLY", default=False),
        "cache_folder": str(os.getenv("CAREER_RAG_MODEL_CACHE", "") or "").strip(),
        "requested_device": str(os.getenv("CAREER_RAG_DEVICE", "cuda") or "cuda").strip().lower(),
        "backend": _EMBEDDER_BACKEND,
        "device": _EMBEDDER_DEVICE,
        "gpu_dtype": _EMBEDDER_DTYPE,
        "gpu_dtype_env": _resolve_gpu_dtype_flag(default="float16"),
        "tf32_enabled": _env_flag("CAREER_RAG_ENABLE_TF32", default=True),
        "error": _EMBEDDER_ERROR,
        "embed_batch_size": _resolve_embed_batch_size(256 if _EMBEDDER_DEVICE == "cuda" else 64),
        "query_batch_size": _resolve_query_batch_size(32),
        "torch_version": "",
        "torch_cuda_version": "",
        "torch_cuda_available": False,
        "torch_cuda_device_count": 0,
        "torch_cuda_device_name": "",
    }
    try:
        torch = _get_torch_module()
        if torch is None:
            raise RuntimeError("torch not installed")

        info["torch_version"] = str(getattr(torch, "__version__", "") or "")
        info["torch_cuda_version"] = str(getattr(getattr(torch, "version", None), "cuda", "") or "")
        info["torch_cuda_available"] = _torch_cuda_available(torch)
        if info["torch_cuda_available"]:
            info["torch_cuda_device_count"] = int(getattr(torch.cuda, "device_count", lambda: 0)())
            current_device = int(getattr(torch.cuda, "current_device", lambda: 0)())
            info["torch_cuda_device_name"] = str(getattr(torch.cuda, "get_device_name", lambda _idx: "")(current_device) or "")
    except Exception as exc:
        info["error"] = str(exc)
    return info


def _resolve_embed_batch_size(default_size: int) -> int:
    return _env_int("CAREER_RAG_BATCH_SIZE", default=max(8, int(default_size)), minimum=8, maximum=1024)


def _resolve_query_batch_size(default_size: int) -> int:
    return _env_int("CAREER_RAG_QUERY_BATCH", default=max(1, int(default_size)), minimum=1, maximum=512)


def _adaptive_embed_batch_size(texts: List[str], default_size: int) -> int:
    """根据文本平均长度自适应批量，降低长文本场景显存峰值。"""
    base = _resolve_embed_batch_size(default_size)
    if not texts:
        return base

    sample = texts[: min(len(texts), 32)]
    avg_len = int(sum(len(x) for x in sample) / max(1, len(sample)))
    if avg_len >= 1800:
        return max(8, base // 4)
    if avg_len >= 900:
        return max(8, base // 2)
    return base


def _hash_token(value: str, prefix: str, length: int = 24) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith(prefix):
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}{digest}"


def _mask_company(company: str) -> str:
    text = str(company or "").strip()
    if not text:
        return ""
    if len(text) <= 2:
        return "**"
    return text[:2] + "***"


def _compute_dedup_key(job: Dict[str, Any]) -> str:
    job_id = str(job.get("job_id", "")).strip()
    if job_id:
        return f"job_id:{job_id}"

    parts = [
        str(job.get("job_name", "")).strip(),
        str(job.get("company_name", "")).strip(),
        str(job.get("city_name", "")).strip(),
        str(job.get("salary_desc", "")).strip(),
    ]
    return "fallback:" + "|".join(parts)


def _desensitize_job_record(job: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(job)

    original_job_id = str(data.get("job_id", "") or "").strip()
    if original_job_id:
        data["job_id"] = _hash_token(original_job_id, "jid_")

    data["company_name"] = _mask_company(str(data.get("company_name", "") or ""))
    existing_dedup = str(data.get("dedup_key", "") or "").strip()
    if existing_dedup.startswith("dk_"):
        data["dedup_key"] = existing_dedup
    else:
        data["dedup_key"] = _hash_token(_compute_dedup_key(job), "dk_", length=32)

    return data


def _parse_time_to_epoch(value: str) -> int:
    text = str(value or "").strip()
    if not text:
        return int(datetime.now().timestamp())
    try:
        return int(datetime.fromisoformat(text).timestamp())
    except Exception:
        return int(datetime.now().timestamp())


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _tokens_for_embedding(text: str) -> List[str]:
    raw = str(text or "").lower()
    if not raw:
        return []

    tokens = _TOKEN_PATTERN.findall(raw)
    if not tokens:
        return []

    # Add bi-grams to improve phrase matching for Chinese and mixed text.
    bigrams = [tokens[i] + tokens[i + 1] for i in range(len(tokens) - 1)]
    return tokens + bigrams


def _hash_embed_text(text: str, dim: int = _VECTOR_DIM) -> List[float]:
    raw_text = str(text or "").strip()
    vec = [0.0] * dim
    tokens = _tokens_for_embedding(raw_text)
    if not tokens:
        return vec
    for token in tokens:
        # 使用更强的哈希并增加盐值
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        # 将一个 token 映射到多个位置以增加特征表达
        for i in range(3):
            sub_digest = hashlib.sha256((digest + str(i)).encode("utf-8")).hexdigest()
            idx = int(sub_digest[:8], 16) % dim
            sign = 1.0 if (int(sub_digest[8:10], 16) % 2 == 0) else -1.0
            vec[idx] += sign

    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 1e-12:
        return vec
    return [x / norm for x in vec]


def _encode_dense_with_backoff(embedder: Any, texts: List[str], batch_size: int, device: str) -> Any:
    torch_module = _get_torch_module()
    current_bs = max(8, int(batch_size))
    while True:
        try:
            with (
                torch_module.inference_mode()
                if torch_module is not None and hasattr(torch_module, "inference_mode")
                else nullcontext()
            ):
                with (
                    torch_module.autocast(device_type="cuda", dtype=getattr(torch_module, _EMBEDDER_DTYPE, None))
                    if (
                        device == "cuda"
                        and torch_module is not None
                        and hasattr(torch_module, "autocast")
                        and _EMBEDDER_DTYPE in {"float16", "bfloat16"}
                    )
                    else nullcontext()
                ):
                    return embedder.encode(
                        texts,
                        normalize_embeddings=True,
                        convert_to_numpy=True,
                        batch_size=current_bs,
                        show_progress_bar=False,
                    )
        except Exception as exc:
            message = str(exc).lower()
            # 遇到显存不足时自动减小批量，尽量继续走 GPU。
            if device == "cuda" and _is_cuda_oom_error(message):
                if torch_module is not None and getattr(torch_module, "cuda", None):
                    try:
                        torch_module.cuda.empty_cache()
                    except Exception:
                        pass
                if current_bs > 8:
                    current_bs = max(8, current_bs // 2)
                    continue
            raise


def _embed_texts(texts: List[str], dim: int = _VECTOR_DIM) -> List[List[float]]:
    global _EMBEDDER_BACKEND
    global _EMBEDDER_ERROR

    normalized_texts = [str(x or "").strip() for x in texts]
    if not normalized_texts:
        return []

    empty_vector = [0.0] * dim
    vectors_out: List[List[float]] = [list(empty_vector) for _ in normalized_texts]
    unique_texts: List[str] = []
    text_to_indexes: Dict[str, List[int]] = {}

    for idx, text in enumerate(normalized_texts):
        if not text:
            continue
        if text in text_to_indexes:
            text_to_indexes[text].append(idx)
        else:
            text_to_indexes[text] = [idx]
            unique_texts.append(text)

    if not unique_texts:
        return vectors_out

    embedder = _load_sentence_transformer()
    if embedder is not None:
        try:
            default_bs = 256 if _EMBEDDER_DEVICE == "cuda" else 64
            batch_size = _adaptive_embed_batch_size(unique_texts, default_bs)
            dense_matrix = _encode_dense_with_backoff(embedder, unique_texts, batch_size, device=_EMBEDDER_DEVICE)

            unique_vectors: List[List[float]] = []
            for dense in dense_matrix:
                raw_values = dense.tolist() if hasattr(dense, "tolist") else list(dense)
                vector = [float(x) for x in raw_values]
                if len(vector) >= dim:
                    unique_vectors.append(vector[:dim])
                else:
                    unique_vectors.append(vector + [0.0] * (dim - len(vector)))

            for unique_idx, text in enumerate(unique_texts):
                vector = unique_vectors[unique_idx] if unique_idx < len(unique_vectors) else list(empty_vector)
                for original_idx in text_to_indexes.get(text, []):
                    vectors_out[original_idx] = list(vector)

            _EMBEDDER_BACKEND = "sentence-transformers"
            _EMBEDDER_ERROR = ""
            return vectors_out
        except Exception as exc:
            # 推理异常时回退哈希向量，保障线上流程不中断。
            _EMBEDDER_BACKEND = "hash-fallback"
            _EMBEDDER_ERROR = str(exc)

    fallback_vectors = [_hash_embed_text(text, dim=dim) for text in unique_texts]
    for unique_idx, text in enumerate(unique_texts):
        vector = fallback_vectors[unique_idx] if unique_idx < len(fallback_vectors) else list(empty_vector)
        for original_idx in text_to_indexes.get(text, []):
            vectors_out[original_idx] = list(vector)
    return vectors_out


def _embed_text(text: str, dim: int = _VECTOR_DIM) -> List[float]:
    raw_text = str(text or "").strip()
    if not raw_text:
        return [0.0] * dim
    return _embed_texts([raw_text], dim=dim)[0]


def _build_rag_document(job: Dict[str, Any]) -> str:
    skills = job.get("skills") or []
    labels = job.get("job_labels") or []
    if not isinstance(skills, list):
        skills = []
    if not isinstance(labels, list):
        labels = []

    parts = [
        f"岗位: {str(job.get('job_name', '') or '').strip()}",
        f"公司: {str(job.get('company_name', '') or '').strip()}",
        f"展示薪资: {str(job.get('salary_desc', '') or '').strip()}",
        f"经验: {str(job.get('experience', '') or '').strip()}",
        f"学历: {str(job.get('education', '') or '').strip()}",
        f"行业: {str(job.get('industry', '') or '').strip()}",
        f"公司规模: {str(job.get('company_scale', '') or '').strip()}",
        f"技能要求: {'、'.join([str(x) for x in (job.get('skills') or []) if str(x).strip()])}",
        f"标签: {'、'.join([str(x) for x in (job.get('job_labels') or []) if str(x).strip()])}",
        f"职责描述: {str(job.get('job_description', '') or '').strip()}",
    ]
    return "\n".join(parts)


def _metadata_from_job(job: Dict[str, Any], inserted_at: str) -> Dict[str, Any]:
    return {
        "dedup_key": str(job.get("dedup_key", "") or ""),
        "job_id": str(job.get("job_id", "") or ""),
        "job_name": str(job.get("job_name", "") or ""),
        "salary_desc": str(job.get("salary_desc", "") or ""),
        "salary_min": _safe_int(job.get("salary_min", 0)),
        "salary_max": _safe_int(job.get("salary_max", 0)),
        "salary_months": _safe_int(job.get("salary_months", 0)),
        "city_name": str(job.get("city_name", "") or ""),
        "area_district": str(job.get("area_district", "") or ""),
        "business_district": str(job.get("business_district", "") or ""),
        "experience": str(job.get("experience", "") or ""),
        "education": str(job.get("education", "") or ""),
        "job_type": str(job.get("job_type", "") or ""),
        "skills_json": json.dumps(job.get("skills", []) or [], ensure_ascii=False),
        "job_labels_json": json.dumps(job.get("job_labels", []) or [], ensure_ascii=False),
        "company_name": str(job.get("company_name", "") or ""),
        "company_scale": str(job.get("company_scale", "") or ""),
        "industry": str(job.get("industry", "") or ""),
        "job_description": str(job.get("job_description", "") or ""),
        "url": str(job.get("url", job.get("job_href", "")) or ""),
        "address": str(job.get("address", "") or ""),
        "scraped_at": str(job.get("scraped_at", "") or ""),
        "inserted_at": str(inserted_at or ""),
        "inserted_ts": _parse_time_to_epoch(inserted_at),
    }


def _job_from_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": str(metadata.get("job_id", "") or ""),
        "job_name": str(metadata.get("job_name", "") or ""),
        "salary_desc": str(metadata.get("salary_desc", "") or ""),
        "salary_min": _safe_int(metadata.get("salary_min", 0)),
        "salary_max": _safe_int(metadata.get("salary_max", 0)),
        "salary_months": _safe_int(metadata.get("salary_months", 0)),
        "city_name": str(metadata.get("city_name", "") or ""),
        "area_district": str(metadata.get("area_district", "") or ""),
        "business_district": str(metadata.get("business_district", "") or ""),
        "experience": str(metadata.get("experience", "") or ""),
        "education": str(metadata.get("education", "") or ""),
        "job_type": str(metadata.get("job_type", "") or ""),
        "skills": _parse_json_list(metadata.get("skills_json", "[]")),
        "job_labels": _parse_json_list(metadata.get("job_labels_json", "[]")),
        "company_name": str(metadata.get("company_name", "") or ""),
        "company_scale": str(metadata.get("company_scale", "") or ""),
        "industry": str(metadata.get("industry", "") or ""),
        "job_description": str(metadata.get("job_description", "") or ""),
        "url": str(metadata.get("url", "") or ""),
        "address": str(metadata.get("address", "") or ""),
        "scraped_at": str(metadata.get("scraped_at", "") or ""),
        "inserted_at": str(metadata.get("inserted_at", "") or ""),
    }


def _parse_json_list(value: Any) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        return []
    return []


def _collection_for_data_dir(data_dir: Path) -> Any:
    chromadb = _load_chromadb()
    storage_path = data_dir / VECTOR_DB_DIR
    storage_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(storage_path))
    return client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def _chunked(items: List[Any], chunk_size: int) -> Iterable[List[Any]]:
    size = max(1, int(chunk_size))
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _upsert_jobs_to_vector_store(
    jobs_data: List[Dict[str, Any]],
    data_dir: Path,
) -> Dict[str, int]:
    data_dir.mkdir(parents=True, exist_ok=True)
    collection = _collection_for_data_dir(data_dir)

    if not jobs_data:
        return {"total": 0, "inserted": 0, "duplicated": 0}

    prepared_ids: List[str] = []
    prepared_docs: List[str] = []
    prepared_metas: List[Dict[str, Any]] = []
    now = datetime.now().isoformat()
    for job in jobs_data:
        sanitized = _desensitize_job_record(job)
        dedup_key = str(sanitized.get("dedup_key", "") or "").strip()
        if not dedup_key:
            continue

        metadata = _metadata_from_job(sanitized, inserted_at=now)
        document = _build_rag_document(sanitized)

        prepared_ids.append(dedup_key)
        prepared_docs.append(document)
        prepared_metas.append(metadata)

    if not prepared_ids:
        return {"total": len(jobs_data), "inserted": 0, "duplicated": len(jobs_data)}

    prepared_embs = _embed_texts(prepared_docs)

    existing_ids: set[str] = set()
    for id_chunk in _chunked(prepared_ids, 200):
        existing = collection.get(ids=id_chunk)
        for item in existing.get("ids") or []:
            existing_ids.add(str(item))

    for start in range(0, len(prepared_ids), 200):
        end = start + 200
        collection.upsert(
            ids=prepared_ids[start:end],
            documents=prepared_docs[start:end],
            metadatas=prepared_metas[start:end],
            embeddings=prepared_embs[start:end],
        )

    inserted = sum(1 for x in prepared_ids if x not in existing_ids)
    duplicated = len(prepared_ids) - inserted
    ignored = max(0, len(jobs_data) - len(prepared_ids))

    return {
        "total": len(jobs_data),
        "inserted": inserted,
        "duplicated": duplicated + ignored,
    }


def upsert_jobs_to_vector_store(jobs_data: List[Dict[str, Any]], data_dir: Path) -> Dict[str, int]:
    with _DB_LOCK:
        return _upsert_jobs_to_vector_store(jobs_data, data_dir)


def schedule_upsert_jobs_to_vector_store(jobs_data: List[Dict[str, Any]], data_dir: Path) -> threading.Thread:
    payload = [dict(item) for item in jobs_data]

    def _worker() -> None:
        try:
            upsert_jobs_to_vector_store(payload, data_dir)
        except Exception:
            return

    thread = threading.Thread(target=_worker, daemon=True, name="career-vector-upsert")
    thread.start()
    return thread


def _fetch_candidates_by_semantic_queries(
    data_dir: Path,
    query_texts: List[str],
    city_name: str,
    top_k: int,
) -> List[List[Dict[str, Any]]]:
    normalized_queries = [str(x or "").strip() for x in query_texts]
    if not normalized_queries:
        return []

    collection = _collection_for_data_dir(data_dir)
    where = {"city_name": city_name} if city_name else None
    all_rows: List[List[Dict[str, Any]]] = []
    query_batch_size = _resolve_query_batch_size(32)

    for query_chunk in _chunked(normalized_queries, query_batch_size):
        embeddings_chunk = _embed_texts(query_chunk)
        if not embeddings_chunk:
            all_rows.extend([[] for _ in query_chunk])
            continue

        query_kwargs: Dict[str, Any] = {
            "query_embeddings": embeddings_chunk,
            "n_results": max(1, int(top_k)),
            "include": ["metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        try:
            result = collection.query(**query_kwargs)
        except Exception:
            query_kwargs.pop("where", None)
            result = collection.query(**query_kwargs)

        batch_metadatas = result.get("metadatas") or []
        batch_distances = result.get("distances") or []

        for idx in range(len(query_chunk)):
            metadatas = batch_metadatas[idx] if idx < len(batch_metadatas) and isinstance(batch_metadatas[idx], list) else []
            distances = batch_distances[idx] if idx < len(batch_distances) and isinstance(batch_distances[idx], list) else []

            rows: List[Dict[str, Any]] = []
            for row_idx, metadata in enumerate(metadatas):
                if not isinstance(metadata, dict):
                    continue

                job = _job_from_metadata(metadata)
                job["_distance"] = _safe_float(distances[row_idx]) if row_idx < len(distances) else 1.0
                rows.append(job)

            all_rows.append(rows)

    return all_rows


def _fetch_candidates_by_semantic_query(
    data_dir: Path,
    query_text: str,
    city_name: str,
    top_k: int,
) -> List[Dict[str, Any]]:
    query = str(query_text or "").strip()
    if not query:
        return []
    rows = _fetch_candidates_by_semantic_queries(
        data_dir=data_dir,
        query_texts=[query],
        city_name=city_name,
        top_k=top_k,
    )
    return rows[0] if rows else []


def _score_recent_candidates(
    candidates: List[Dict[str, Any]],
    keyword: str,
    threshold_ts: int,
    days: int,
    limit: int,
) -> List[Dict[str, Any]]:
    kw = str(keyword or "").strip()
    kw_lower = kw.lower()
    safe_days = max(1, int(days))
    safe_limit = max(1, int(limit))

    scored: List[tuple[float, Dict[str, Any]]] = []
    for item in candidates:
        inserted_at = str(item.get("inserted_at", "") or "")
        inserted_ts = _parse_time_to_epoch(inserted_at)
        if inserted_ts < threshold_ts:
            continue

        title = str(item.get("job_name", "") or "")
        desc = str(item.get("job_description", "") or "")
        skills = " ".join([str(x) for x in (item.get("skills", []) or []) if str(x).strip()])
        title_lower = title.lower()
        desc_lower = desc.lower()
        skills_lower = skills.lower()

        keyword_boost = 0.0
        if kw_lower and kw_lower in title_lower:
            keyword_boost += 0.4
        if kw_lower and kw_lower in desc_lower:
            keyword_boost += 0.2
        if kw_lower and kw_lower in skills_lower:
            keyword_boost += 0.2

        distance = _safe_float(item.pop("_distance", 1.0))
        # chromadb cosine 返回 1-cosine_similarity，距离越小越相似。
        semantic_score = max(0.0, 1.0 - distance)

        # 标题不匹配关键词时降低语义分，减少无关结果进入 topK。
        title_match = (kw_lower in title_lower) if kw_lower else True
        if not title_match:
            semantic_score *= 0.5

        freshness_score = min(1.0, max(0.0, (inserted_ts - threshold_ts) / max(1, safe_days * 86400)))
        total_score = semantic_score * 0.8 + keyword_boost + freshness_score * 0.1
        scored.append((total_score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:safe_limit]]


def fetch_recent_jobs_by_city_keywords(
    data_dir: Path,
    city_name: str,
    keywords: List[str],
    days: int = 30,
    limit: int = 500,
) -> List[List[Dict[str, Any]]]:
    city = str(city_name or "").strip()
    normalized_keywords = [str(x or "").strip() for x in keywords]
    if not normalized_keywords:
        return []
    if not city:
        return [[] for _ in normalized_keywords]

    valid_pairs = [(idx, kw) for idx, kw in enumerate(normalized_keywords) if kw]
    if not valid_pairs:
        return [[] for _ in normalized_keywords]

    safe_days = max(1, int(days))
    safe_limit = max(1, int(limit))
    data_dir.mkdir(parents=True, exist_ok=True)

    with _DB_LOCK:
        threshold_dt = datetime.now() - timedelta(days=safe_days)
        threshold_ts = int(threshold_dt.timestamp())

        query_texts = [f"{kw} {kw} {city}" for _, kw in valid_pairs]
        candidates_by_query = _fetch_candidates_by_semantic_queries(
            data_dir=data_dir,
            query_texts=query_texts,
            city_name=city,
            top_k=max(safe_limit * 4, 100),
        )

    results: List[List[Dict[str, Any]]] = [[] for _ in normalized_keywords]
    for pair_idx, (original_idx, kw) in enumerate(valid_pairs):
        candidates = candidates_by_query[pair_idx] if pair_idx < len(candidates_by_query) else []
        results[original_idx] = _score_recent_candidates(
            candidates=candidates,
            keyword=kw,
            threshold_ts=threshold_ts,
            days=safe_days,
            limit=safe_limit,
        )

    return results


def fetch_recent_jobs_by_city_keyword(
    data_dir: Path,
    city_name: str,
    keyword: str,
    days: int = 30,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    city = str(city_name or "").strip()
    kw = str(keyword or "").strip()
    if not city or not kw:
        return []

    rows_by_keyword = fetch_recent_jobs_by_city_keywords(
        data_dir=data_dir,
        city_name=city,
        keywords=[kw],
        days=days,
        limit=limit,
    )
    return rows_by_keyword[0] if rows_by_keyword else []


def _rows_to_rag_context(rows: List[Dict[str, Any]], top_k: int) -> str:
    snippets: List[str] = []
    for idx, item in enumerate(rows[: max(1, int(top_k))], start=1):
        snippets.append(
            "\n".join(
                [
                    f"[岗位{idx}] {item.get('job_name', '')}",
                    f"公司: {item.get('company_name', '')} | 城市: {item.get('city_name', '')} | 薪资: {item.get('salary_desc', '')}",
                    f"经验/学历: {item.get('experience', '')} / {item.get('education', '')}",
                    f"技能: {'、'.join(item.get('skills', [])[:8])}",
                    f"职责摘要: {str(item.get('job_description', '') or '')[:200]}",
                    f"链接: {item.get('url', '')}",
                ]
            )
        )
    return "\n\n".join(snippets)


def build_rag_contexts_for_queries(
    data_dir: Path,
    query_texts: List[str],
    city_name: str = "",
    days: int = 30,
    top_k: int = 8,
) -> List[str]:
    normalized_queries = [str(x or "").strip() for x in query_texts]
    if not normalized_queries:
        return []

    contexts = ["" for _ in normalized_queries]
    valid_pairs = [(idx, query) for idx, query in enumerate(normalized_queries) if query]
    if not valid_pairs:
        return contexts

    safe_top_k = max(1, int(top_k))
    effective_city = str(city_name or "").strip() or "全国"

    ranked_rows_by_query = fetch_recent_jobs_by_city_keywords(
        data_dir=data_dir,
        city_name=effective_city,
        keywords=[query for _, query in valid_pairs],
        days=days,
        limit=safe_top_k,
    )

    fallback_targets: List[int] = []
    fallback_queries: List[str] = []
    for local_idx, (original_idx, query) in enumerate(valid_pairs):
        rows = ranked_rows_by_query[local_idx] if local_idx < len(ranked_rows_by_query) else []
        if rows:
            contexts[original_idx] = _rows_to_rag_context(rows, safe_top_k)
        else:
            fallback_targets.append(original_idx)
            fallback_queries.append(query)

    # 城市过滤过严时，批量回退到全量语义检索。
    if fallback_queries:
        with _DB_LOCK:
            fallback_candidates_by_query = _fetch_candidates_by_semantic_queries(
                data_dir=data_dir,
                query_texts=fallback_queries,
                city_name="",
                top_k=max(safe_top_k * 3, 20),
            )
        for local_idx, target_idx in enumerate(fallback_targets):
            rows = fallback_candidates_by_query[local_idx] if local_idx < len(fallback_candidates_by_query) else []
            contexts[target_idx] = _rows_to_rag_context(rows, safe_top_k)

    return contexts


def build_rag_context_for_query(
    data_dir: Path,
    query_text: str,
    city_name: str = "",
    days: int = 30,
    top_k: int = 8,
) -> str:
    query = str(query_text or "").strip()
    if not query:
        return ""

    contexts = build_rag_contexts_for_queries(
        data_dir=data_dir,
        query_texts=[query],
        city_name=city_name,
        days=days,
        top_k=top_k,
    )
    return contexts[0] if contexts else ""


def load_all_jobs_from_vector_store(data_dir: Path, limit: int = 50000) -> List[Dict[str, Any]]:
    data_dir.mkdir(parents=True, exist_ok=True)

    with _DB_LOCK:
        collection = _collection_for_data_dir(data_dir)

        rows: List[Dict[str, Any]] = []
        offset = 0
        batch_size = 500

        while len(rows) < max(1, int(limit)):
            batch = collection.get(limit=batch_size, offset=offset, include=["metadatas"])
            metadatas = batch.get("metadatas") or []
            if not metadatas:
                break

            for metadata in metadatas:
                if not isinstance(metadata, dict):
                    continue
                rows.append(_job_from_metadata(metadata))
                if len(rows) >= limit:
                    break
            offset += len(metadatas)

    rows.sort(key=lambda x: str(x.get("inserted_at", "") or ""), reverse=True)
    return rows


def desensitize_existing_jobs(data_dir: Path) -> Dict[str, int]:
    data_dir.mkdir(parents=True, exist_ok=True)

    with _DB_LOCK:
        collection = _collection_for_data_dir(data_dir)

        all_rows = collection.get(include=["documents", "metadatas", "embeddings"])
        ids = all_rows.get("ids") or []
        metas = all_rows.get("metadatas") or []
        embs = all_rows.get("embeddings") or []

        updated = 0
        new_metas: List[Dict[str, Any]] = []
        new_docs: List[str] = []
        new_embs: List[List[float]] = []

        for idx, metadata in enumerate(metas):
            if not isinstance(metadata, dict):
                continue

            original = _job_from_metadata(metadata)
            sanitized = _desensitize_job_record(original)
            if sanitized.get("job_id", "") != original.get("job_id", "") or sanitized.get("company_name", "") != original.get("company_name", ""):
                updated += 1

            inserted_at = str(metadata.get("inserted_at", "") or datetime.now().isoformat())
            new_metas.append(_metadata_from_job(sanitized, inserted_at=inserted_at))
            new_docs.append(_build_rag_document(sanitized))
            if idx < len(embs) and isinstance(embs[idx], list) and embs[idx]:
                new_embs.append([_safe_float(x) for x in embs[idx]])
            else:
                new_embs.append(_embed_text(new_docs[-1]))

        if ids:
            collection.upsert(ids=ids, documents=new_docs, metadatas=new_metas, embeddings=new_embs)

    return {"total": len(ids), "updated": updated}
