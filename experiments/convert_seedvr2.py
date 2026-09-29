"""Convert SeedVR2 .pth state dict to use 'model.diffusion_model.' prefix
to match ComfyUI's model_detection.py expectations."""
import torch
from pathlib import Path

SRC = Path(r'E:/ComfyUI/models/seedvr2/seedvr2_ema_3b.pth')
DST = Path(r'E:/ComfyUI/models/diffusion_models/seedvr2_ema_3b.safetensors')

print(f'Loading {SRC.name}...')
sd = torch.load(str(SRC), map_location='cpu', weights_only=False)

# Add 'model.diffusion_model.' prefix to all keys (including conditioning buffers)
new_sd = {}
for k, v in sd.items():
    new_sd[f'model.diffusion_model.{k}'] = v

# Also add positive_conditioning and negative_conditioning as zeros
# (required keys per supported_models.py line 1764-1767)
# These need to be inside the prefix to survive state_dict_prefix_replace with filter_keys=True
new_sd['model.diffusion_model.positive_conditioning'] = torch.zeros(58, 5120)
new_sd['model.diffusion_model.negative_conditioning'] = torch.zeros(64, 5120)

print(f'Total keys: {len(new_sd)}')

# Save as safetensors for safe loading
from safetensors.torch import save_file
print(f'Saving {DST.name}...')
# convert tensors to contiguous for safetensors
cont_sd = {k: v.contiguous() for k, v in new_sd.items()}
save_file(cont_sd, str(DST))
print(f'Saved: {DST}')
print(f'  size: {DST.stat().st_size/1e9:.2f}GB')