"""CLIP zero-shot gates for pipeline inputs (optional; returns None if open_clip is unavailable)."""
import numpy as np
_model = None
def _load():
    global _model
    if _model is None:
        import torch, open_clip
        m, _, pre = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k"); tok = open_clip.get_tokenizer("ViT-B-32")
        _model = (m, pre, tok, torch)
    return _model
def zero_shot(image_bgr, prompts):
    """Return softmax probabilities over `prompts` (list of str) for the image, or None if CLIP unavailable."""
    try: m, pre, tok, torch = _load()
    except Exception: return None
    from PIL import Image
    import cv2
    im = pre(Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))).unsqueeze(0)
    with torch.no_grad():
        v = m.encode_image(im); v /= v.norm(dim=-1, keepdim=True); t = m.encode_text(tok(prompts)); t /= t.norm(dim=-1, keepdim=True)
        return (100 * v @ t.T).softmax(-1)[0].numpy()
WHOLE_JEANS = ["a photo of a complete pair of jeans showing the waistband, pockets and fly, laid flat or hanging",
               "a cropped photo showing only the legs of jeans, no waistband or pockets visible",
               "a person wearing jeans", "a close-up of denim fabric or a hem"]
def whole_garment_probability(image_bgr):
    p = zero_shot(image_bgr, WHOLE_JEANS); return None if p is None else float(p[0])
