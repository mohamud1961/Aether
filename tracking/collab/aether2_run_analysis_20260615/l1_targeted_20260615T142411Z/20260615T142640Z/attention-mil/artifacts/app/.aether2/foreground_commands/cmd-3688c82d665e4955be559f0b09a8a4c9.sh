python3 - <<'PY'
import torch
from abmil_assignment import ABMIL

for dtype in (torch.float32, torch.float64):
    torch.manual_seed(0)
    model = ABMIL(input_dim=16, hidden_dim=8, n_classes=3).to(dtype=dtype)
    model.eval()
    X = torch.randn(11, 16, dtype=dtype, requires_grad=True)
    logits, attn = model(X)
    assert logits.shape == (1, 3)
    assert attn.shape == (11, 1)
    s = attn.sum().detach().cpu().item()
    assert abs(s - 1.0) < (1e-6 if dtype==torch.float32 else 1e-10)
    loss = logits.sum()
    loss.backward()
    assert torch.isfinite(X.grad).all()
    print(dtype, 'ok', float(s))

model = ABMIL(input_dim=32, hidden_dim=16, n_classes=2)
model.eval()
X = torch.randn(50000, 32)
with torch.no_grad():
    logits, attn = model(X)
print('large', logits.shape, attn.shape, float(attn.sum()))
PY