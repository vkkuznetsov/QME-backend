#!/usr/bin/env python
# ────────────────────────────────────────────────────────────────
#  recommend_train_v4.py  – Two-Tower с тёплым стартом, in-batch
#                           negatives и «мягкими» hard-negatives
# ────────────────────────────────────────────────────────────────
"""
Запуск:

    python recommend_train_v4.py
        --epochs 40          \          # ≤ 40 эпох с early-stop
        --tau 0.08           \          # температура InfoNCE
        --accum 4            \          # grad-accum (эфф. batch≈4096)
        --hard_k 1                      # по 1 hard-neg

После обучения появится student_tower.onnx – её можно
подключать в PL/Python-UDF и выполнять

    ORDER BY student_embed(uid) <=> elective.text_embed LIMIT 10
"""
import argparse, asyncio, logging, random
import math
from pathlib import Path

import numpy as np
import torch
from torch import nn, optim
from torch.utils.data import Dataset, DataLoader

# ── DB-модули проекта ----------------------------------------------------------
from backend.database.database import db_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database.models.student import Student, student_group
from backend.database.models.group import Group
from backend.database.models.elective import Elective

# ── reproducibility ------------------------------------------------------------
SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)
random.seed(SEED)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ───────────────────────────────────────────────────────────────────────────────
# 1. ПАРАМЕТРЫ CLI
# ───────────────────────────────────────────────────────────────────────────────
def get_args():
    p = argparse.ArgumentParser(prog="recommend_train_v4")
    p.add_argument("--epochs", type=int, default=200)
    p.add_argument("--tau", type=float, default=0.1,
                   help="температура в InfoNCE (0.07-0.1)")
    p.add_argument("--accum", type=int, default=4,
                   help="шагов grad-accum для крупного batch")
    p.add_argument("--hard_k", type=int, default=328,
                   help="сколько hard-negatives добавлять")
    return p.parse_args()

# ───────────────────────────────────────────────────────────────────────────────
# 2. ЗАГРУЗКА ТЕНЗОРОВ
# ───────────────────────────────────────────────────────────────────────────────
@db_session
async def load_tensors(db: AsyncSession):
    # --- студенты --------------------------------------------------------------
    res = await db.execute(select(Student))
    students = res.scalars().all()

    codes     = sorted({s.sp_code for s in students})
    profiles  = sorted({s.sp_profile for s in students})
    code2idx  = {c: i for i, c in enumerate(codes)}
    prof2idx  = {p: i for i, p in enumerate(profiles)}

    feats, code_lbl, prof_lbl, id2user = [], [], [], {}
    for idx, s in enumerate(students):
        feats.append(np.hstack([s.competencies,
                                list(s.diagnostics.values())]))      # (10,)
        code_lbl.append(code2idx[s.sp_code])
        prof_lbl.append(prof2idx[s.sp_profile])
        id2user[s.id] = idx

    feats = np.vstack(feats).astype("float32")
    mu, sigma = feats.mean(0), feats.std(0) + 1e-9         # z-score
    feats = (feats - mu) / sigma

    X_users = torch.from_numpy(
        np.hstack([feats,
                   np.array(code_lbl)[:, None],
                   np.array(prof_lbl)[:, None]])
    ).float()                                              # (U,12)

    # --- элективы --------------------------------------------------------------
    res_e = await db.execute(select(Elective))
    electives = res_e.scalars().all()
    id2item, embeds = {}, []
    for e in electives:
        if e.text_embed is not None:
            id2item[e.id] = len(embeds)
            embeds.append(e.text_embed)
    X_items = torch.tensor(np.array(embeds), dtype=torch.float32)    # (I,384)

    # --- пары (u,i) ------------------------------------------------------------
    res_p = await db.execute(
        select(Student.id, Group.elective_id)
        .join(student_group, student_group.c.student_id == Student.id)
        .join(Group,        student_group.c.group_id   == Group.id)
    )
    pairs = {(id2user[s], id2item[e]) for s, e in res_p
             if s in id2user and e in id2item}
    pairs = torch.tensor(list(pairs), dtype=torch.int64)             # (K,2)

    logging.info(f"Users : {X_users.shape}  | "
                 f"Items : {X_items.shape}  | "
                 f"Pairs : {pairs.shape}")
    return X_users, X_items, pairs

# ───────────────────────────────────────────────────────────────────────────────
# 3. DATASET
# ───────────────────────────────────────────────────────────────────────────────
class ContrastiveDS(Dataset):
    def __init__(self, pairs):          # pairs: (K,2)
        self.u  = pairs[:, 0]
        self.ip = pairs[:, 1]

    def __len__(self):  return len(self.u)
    def __getitem__(self, idx):
        return self.u[idx], self.ip[idx]

# ───────────────────────────────────────────────────────────────────────────────
# 4. МОДЕЛЬ
# ───────────────────────────────────────────────────────────────────────────────
class StudentTower(nn.Module):
    def __init__(self, n_code, n_prof, d_num=10, d_out=384):
        super().__init__()
        self.emb_code = nn.Embedding(n_code, 32)
        self.emb_prof = nn.Embedding(n_prof, 32)
        self.mlp = nn.Sequential(
            nn.Linear(d_num + 64, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(128, d_out)
        )
    def forward(self, num, code, prof):
        cat = torch.cat([self.emb_code(code), self.emb_prof(prof)], dim=-1)
        x   = torch.cat([num, cat], dim=-1)
        return nn.functional.normalize(self.mlp(x), dim=-1)          # (B,384)

class ItemTower(nn.Module):
    def __init__(self, d=384):
        super().__init__()
        self.proj = nn.Linear(d, d)
    def forward(self, x):
        return nn.functional.normalize(self.proj(x), dim=-1)

# ───────────────────────────────────────────────────────────────────────────────
# 5. HARD NEGATIVE МИНЁР
# ───────────────────────────────────────────────────────────────────────────────
def build_hard_neg(stu, itm, X_users, X_items, pairs, k=1):
    with torch.no_grad():
        u_vec = stu(X_users[:, :10].to(DEVICE),
                    X_users[:, -2].long().to(DEVICE),
                    X_users[:, -1].long().to(DEVICE))
        i_vec = itm(X_items.to(DEVICE))
        sims  = u_vec @ i_vec.T                                   # (U,I)

    dic = {}
    for (u, ip) in pairs.tolist():
        s = sims[u].clone()
        s[ip] = -1.0
        dic[(u, ip)] = s.topk(k).indices.cpu().tolist()
    return dic

# ───────────────────────────────────────────────────────────────────────────────
# 6. ОБУЧЕНИЕ
# ───────────────────────────────────────────────────────────────────────────────
def train(args, X_users, X_items, pairs):
    # train/val split by user
    u_unique = torch.unique(pairs[:, 0])
    val_u = set(random.sample(u_unique.tolist(), int(0.2 * len(u_unique))))
    msk   = torch.tensor([u.item() in val_u for u in pairs[:, 0]])
    train_p, val_p = pairs[~msk], pairs[msk]
    logging.info(f"Training pairs count: {len(train_p)}")
    logging.info(f"Hyperparameters: epochs={args.epochs}, tau={args.tau}, accum_steps={args.accum}, hard_k={args.hard_k}")

    dl_train = DataLoader(ContrastiveDS(train_p), batch_size=16, shuffle=True)
    dl_val   = DataLoader(ContrastiveDS(val_p),   batch_size=16)

    code_card = int(X_users[:, -2].max()+1)
    prof_card = int(X_users[:, -1].max()+1)
    stu = StudentTower(code_card, prof_card).to(DEVICE)
    itm = ItemTower().to(DEVICE)
    X_items_d = X_items.to(DEVICE)

    opt = optim.AdamW(list(stu.parameters()) + list(itm.parameters()),
                      lr=1e-4, weight_decay=1e-4)
    sch = optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=4)

    # warm-start: заморозка ItemTower на 5 эпох
    for p in itm.parameters():  p.requires_grad_(False)

    hard_neg = build_hard_neg(stu, itm, X_users, X_items, train_p, k=args.hard_k)

    best_recall, patience = 0.0, 0
    for ep in range(1, args.epochs + 1):
        stu.train(); itm.train()
        tot_loss, step_accum = 0.0, 0

        for u, ip in dl_train:
            # случайный негатив
            ir = torch.randint(0, len(X_items), (len(u),), dtype=torch.int64)
            # hard-neg
            ih = torch.tensor([random.choice(hard_neg[(u_i.item(), ip_i.item())])
                               for u_i, ip_i in zip(u, ip)], dtype=torch.int64)

            # эмбеддинги
            u_vec = stu(
                X_users[u, :10].to(DEVICE),
                X_users[u, -2].long().to(DEVICE),
                X_users[u, -1].long().to(DEVICE)
            )
            v_pos  = itm(X_items_d[ip.to(DEVICE)])
            v_rand = itm(X_items_d[ir.to(DEVICE)])
            v_hard = itm(X_items_d[ih.to(DEVICE)])

            # in-batch negatives: positive, rand, hard, shift-pos
            all_v  = torch.cat([v_pos,
                                v_rand,
                                v_hard,
                                v_pos.roll(1, 0)], dim=0)             # (4B,384)
            logits = (u_vec @ all_v.T) / args.tau                      # (B,4B)
            lbl    = torch.arange(len(u_vec), device=DEVICE)
            loss   = nn.functional.cross_entropy(logits, lbl)

            loss.backward()
            step_accum += 1
            if step_accum % args.accum == 0:
                opt.step(); opt.zero_grad()
            tot_loss += loss.item()

        # размораживаем ItemTower после 5 эпох
        if ep == 10:
            for p in itm.parameters(): p.requires_grad_(True)

        # обновляем hard-neg раз в 5 эпох (со 6-й)
        if ep % 5 == 0 and ep > 10:
            hard_neg = build_hard_neg(stu, itm, X_users, X_items, train_p,
                                      k=args.hard_k)

        # ---- validation metrics --------------------------------------------
        import math
        with torch.no_grad():
            stu.eval(); itm.eval()
            hit = tot = 0
            mrr_sum = ndcg_sum = 0.0
            for u, ip in dl_val:
                u_vec = stu(
                    X_users[u, :10].to(DEVICE),
                    X_users[u, -2].long().to(DEVICE),
                    X_users[u, -1].long().to(DEVICE)
                )
                sims = u_vec @ itm(X_items_d).T
                topk = sims.topk(10).indices.cpu()
                for row, true_i in zip(topk, ip):
                    tot += 1
                    # hit for recall
                    hit_flag = int(true_i in row)
                    hit += hit_flag
                    # position of true item (0-based)
                    if hit_flag:
                        pos = (row == true_i).nonzero(as_tuple=True)[0].item()
                        mrr_sum += 1.0 / (pos + 1)
                        ndcg_sum += 1.0 / math.log2(pos + 2)
            recall10 = hit / tot
            precision10 = hit / (tot * 10)
            mrr10 = mrr_sum / tot
            ndcg10 = ndcg_sum / tot
        avg_loss = tot_loss / len(dl_train)
        sch.step(avg_loss)

        if recall10 > best_recall:
            best_recall, patience = recall10, 0
        else:
            patience += 1
        logging.info(
            f"E{ep:02d} "
            f"loss={avg_loss:.4f}  "
            f"recall@10={recall10:.3f}  "
            f"precision@10={precision10:.3f}  "
            f"mrr@10={mrr10:.3f}  "
            f"ndcg@10={ndcg10:.3f}  "
            f"lr={opt.param_groups[0]['lr']:.1e}"
        )
        if patience >= 1000:          # early stop ≈ 6 эпох без роста
            break

    # ---- final results summary --------------------------------------------
    logging.info(
        f"Training completed. Best observed metrics: "
        f"recall@10={best_recall:.3f}, "
        f"precision@10={best_recall/(10):.3f}, "  # approx best precision
        f"mrr@10={mrr10:.3f}, "
        f"ndcg@10={ndcg10:.3f}"
    )
    return stu.cpu()

# ───────────────────────────────────────────────────────────────────────────────
# 7. ЭКСПОРТ
# ───────────────────────────────────────────────────────────────────────────────
def export_onnx(stu: StudentTower):
    path = Path("student_tower.onnx")
    dummy_num  = torch.zeros(1, 10, dtype=torch.float32)
    dummy_code = torch.zeros(1, dtype=torch.int64)
    dummy_prof = torch.zeros(1, dtype=torch.int64)
    torch.onnx.export(stu,
                      (dummy_num, dummy_code, dummy_prof),
                      path,
                      input_names=["num", "code", "prof"],
                      output_names=["embed"],
                      opset_version=17)
    logging.info(f"ONNX-модель сохранена: {path.resolve()}")

# ───────────────────────────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────────────────────────
async def async_main():
    args = get_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")

    X_users, X_items, pairs = await load_tensors()
    stu_best = train(args, X_users, X_items, pairs)
    # export_onnx(stu_best)

if __name__ == "__main__":
    asyncio.run(async_main())
