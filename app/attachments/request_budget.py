from dataclasses import dataclass


@dataclass(frozen=True)
class RequestImageOffloadPolicy:
    max_bytes: int | None = 20 * 1024 * 1024
    max_images: int | None = None
    byte_quantum: int = 10 * 1024 * 1024
    count_quantum: int = 20
    representation: str = "base64"

    def __post_init__(self):
        for value in (self.max_bytes, self.max_images):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Request image budgets must be nonnegative integers")
        if self.byte_quantum <= 0 or self.count_quantum <= 0 or self.representation not in {"raw", "base64"}:
            raise ValueError("Invalid request image offload policy")


def offloaded_image_prefix_count(lengths, policy):
    excess_count = max(0, len(lengths) - policy.max_images) if policy.max_images is not None else 0
    excess_bytes = max(0, sum(lengths) - policy.max_bytes) if policy.max_bytes is not None else 0
    count_target = ((excess_count + policy.count_quantum - 1) // policy.count_quantum) * policy.count_quantum
    byte_target = ((excess_bytes + policy.byte_quantum - 1) // policy.byte_quantum) * policy.byte_quantum
    removed = count = 0
    for length in lengths:
        byte_met = not byte_target or (removed >= byte_target if policy.byte_quantum == 1 else removed > byte_target)
        if count >= count_target and byte_met:
            break
        count += 1
        removed += length
    return count


def walk_images(blocks):
    for block in blocks if isinstance(blocks, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "image" and isinstance(block.get("attachment"), dict):
            yield block
        elif isinstance(block.get("content"), list):
            yield from walk_images(block["content"])


def offload_request_images_with_policy(messages, policy, byte_length, placeholder):
    lengths = [byte_length(b["attachment"]) for m in messages for b in walk_images(m.get("content"))]
    if policy.representation == "base64":
        lengths = [((n + 2) // 3) * 4 for n in lengths]
    remaining = offloaded_image_prefix_count(lengths, policy)

    def project(blocks):
        nonlocal remaining
        if not isinstance(blocks, list):
            return blocks
        out = []
        for block in blocks:
            if block.get("type") == "image" and remaining:
                remaining -= 1
                out.append({"type": "text", "text": placeholder(block["attachment"])})
            elif isinstance(block.get("content"), list):
                out.append({**block, "content": project(block["content"])})
            else:
                out.append(block)
        return out

    return [{**m, "content": project(m.get("content"))} for m in messages]
