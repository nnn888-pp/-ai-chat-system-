# lora.py
# LoRA 低秩微调：冻结原始权重，只训练插入的低秩矩阵 A、B
# 本文件改编自课程参考实现 model_lora.py，补了 merge（合并权重）功能
import torch
import torch.nn as nn

TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj", "out_proj")


class LoRA(nn.Module):
    """B(A(x))：A 降维到 rank，B 再升回原维度，参数量极小"""

    def __init__(self, in_features, out_features, rank):
        super().__init__()
        self.rank = rank
        self.A = nn.Linear(in_features, rank, bias=False)
        self.B = nn.Linear(rank, out_features, bias=False)
        nn.init.normal_(self.A.weight, mean=0.0, std=0.02)
        # B 初始化为 0，保证训练开始时 LoRA 分支输出为 0，不破坏原模型
        nn.init.zeros_(self.B.weight)

    def forward(self, x):
        return self.B(self.A(x))


def apply_lora(model, rank=8):
    """给注意力的 q/k/v/o 投影注入 LoRA（课程要求优先注入 Attention 层）"""
    device = next(model.parameters()).device
    # 先取快照再遍历，避免边遍历边加子模块
    for name, module in list(model.named_modules()):
        if isinstance(module, nn.Linear) and name.split(".")[-1] in TARGETS:
            lora = LoRA(module.in_features, module.out_features, rank).to(device)
            module.add_module("lora", lora)
            original_forward = module.forward

            def forward_with_lora(x, layer1=original_forward, layer2=lora):
                return layer1(x) + layer2(x)

            module.forward = forward_with_lora


def save_lora(model, path):
    """只保存 LoRA 权重（几百 KB），这是 LoRA 最大的优势"""
    state = {}
    for name, module in model.named_modules():
        if hasattr(module, "lora"):
            state.update({f"{name}.lora.{k}": v for k, v in module.lora.state_dict().items()})
    torch.save(state, path)


def load_lora(model, path):
    state = torch.load(path, map_location=next(model.parameters()).device)
    for name, module in model.named_modules():
        if hasattr(module, "lora"):
            part = {k.replace(f"{name}.lora.", ""): v
                    for k, v in state.items() if f"{name}.lora." in k}
            module.lora.load_state_dict(part)


def merge_lora(model):
    """把 B@A 加回原始权重并摘掉 LoRA，推理时零额外开销"""
    for module in model.modules():
        if isinstance(module, nn.Linear) and hasattr(module, "lora"):
            with torch.no_grad():
                module.weight += module.lora.B.weight @ module.lora.A.weight
            del module.lora
            module.forward = nn.Linear.forward.__get__(module, type(module))
