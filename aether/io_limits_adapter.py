from __future__ import annotations

import mimetypes
from typing import Optional, Dict, Any, List, Union

from .artifact_store import ArtifactStore, ArtifactRef
from .policy_config import PolicyConfig


class IOLimitsAdapter:
    """
    PRM-005: Chunked read adapter for large/binary files.
    Preserves truncation metadata and prevents full-content loading of large items.
    """

    def __init__(
        self,
        artifact_store: ArtifactStore,
        policy: PolicyConfig,
        chunk_size_bytes: int = 1024 * 1024,  # 1MB
        preview_bytes: int = 512,
    ) -> None:
        self.artifact_store = artifact_store
        self.policy = policy
        self.chunk_size_bytes = chunk_size_bytes
        self.preview_bytes = preview_bytes

    def process_file_read(
        self,
        filepath: str,
        data: bytes,
        truncation_metadata: Optional[Dict[str, Any]] = None,
    ) -> Union[str, Dict[str, Any]]:
        """
        Processes a file read operation.
        Returns either the full content as string (for small text files when FF off or allowed)
        or a structured artifact dictionary (for large/binary files).
        """
        if not self.policy.feature_flags.ff_io_limits_adapter:
            # Fallback: decode and return as string if possible, else handle as binary placeholder
            return self._passthrough_legacy(filepath, data, truncation_metadata)

        size_bytes = len(data)
        is_binary = self._is_binary(filepath, data)
        
        # Heuristic: treat as large if > chunk_size or if it's binary
        is_large = size_bytes > self.chunk_size_bytes

        if not is_large and not is_binary:
            # Small text file: return content string directly
            # This preserves simple context for configuration files, source code, etc.
            try:
                content_str = data.decode("utf-8")
                # If we have truncation metadata, we still want to attach it somehow?
                # Actually, standard strings don't carry metadata in python.
                # But logical representation downstream will handle it.
                # For small files, we assume the tool did NOT truncate it yet if we have the full bytes here.
                # However, if the tool *did* truncate it (truncation_metadata is set), we might need to represent it.
                # But io_limits_adapter typically receives the RAW bytes read by the system.
                # If truncation happened upstream (e.g. at tool level), then `data` is the truncated content.
                
                # If truncation metadata is present, we SHOULD treat it as an artifact to preserve that metadata
                # because returning a bare string loses the "truncated: true" flag.
                if truncation_metadata and truncation_metadata.get("truncated", False):
                    pass # Go to artifact path
                else:
                    return content_str
            except UnicodeDecodeError:
                # It's actually binary despite name/checks, force artifact path
                pass 

        # It's large, binary, or truncated. Create an artifact.
        
        # 1. Chunking logic (virtual chunking since we have the full blob in memory here from the tool output)
        # In a real streaming implementation, we'd stream. Here we simulate chunking metadata.
        # We store the FULL blob in artifact store, but describe it as chunks in the ref.
        
        offsets: List[Dict[str, int]] = []
        for i in range(0, size_bytes, self.chunk_size_bytes):
            length = min(self.chunk_size_bytes, size_bytes - i)
            offsets.append({"offset": i, "length": length})

        content_type = self._detect_content_type(filepath, is_binary)
        
        artifact_ref = self.artifact_store.put_bytes(
            data,
            content_type=content_type,
            offsets=offsets,
            preview_bytes=self.preview_bytes,
        )

        return self._format_artifact_response(artifact_ref, truncation_metadata)

    def _passthrough_legacy(
        self, 
        filepath: str, 
        data: bytes, 
        truncation_metadata: Optional[Dict[str, Any]]
    ) -> Union[str, Dict[str, Any]]:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return f"<BINARY_FILE path='{filepath}' size='{len(data)}'>"

    def _is_binary(self, filepath: str, data: bytes) -> bool:
        # 1. Check extension mapping
        mime, _ = mimetypes.guess_type(filepath)
        if mime and not mime.startswith("text/"):
            return True
            
        # 2. Check for null bytes in preview
        if b"\x00" in data[:1024]:
            return True
            
        return False

    def _detect_content_type(self, filepath: str, is_binary: bool) -> str:
        mime, _ = mimetypes.guess_type(filepath)
        if mime:
            return mime
        return "application/octet-stream" if is_binary else "text/plain"

    def _format_artifact_response(
        self, 
        ref: ArtifactRef, 
        truncation_metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Returns the structured dictionary expected by the Context Compiler 
        for an item backed by an artifact.
        """
        response = {
            "type": "artifact_ref",
            "artifact_id": ref.artifact_id,
            "preview_ref": ref.preview_ref,
            "size_bytes": ref.size_bytes,
            "content_type": ref.content_type,
            "offsets": ref.offsets,
        }
        
        if truncation_metadata:
            response["truncation"] = truncation_metadata

        return response
