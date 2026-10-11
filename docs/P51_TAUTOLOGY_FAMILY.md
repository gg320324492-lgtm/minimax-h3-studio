# P51 — 三处同形的恒真判据：先测覆盖面，再决定合并

> 结论先行：**不是"合并成一份"，是"合并其中两份，第三份保留并写清为什么"。**
> 四份判据里其实只有三份 —— `test_p46_probe_instruments.py` **根本没有判据**。

---

## 0. 一句话

| 问题 | 答案 |
|---|---|
| 四份判据有几份？ | **三份**。p46 没有任何判据 |
| 有没有互为真子集的？ | 有。**p27 ⊊ p42，p27 ⊊ locked** |
| 合并会丢什么？ | locked 独有的 3 个形状 —— **这是实测的代价，不是顺带的** |
| 合并会让别的文件变红吗？ | **不会。实测三份文件在并集下都是 0 offender** |
| `:771` 完全冗余吗？ | **是。实测证明**，见 §4 |
| 守卫建不建？ | **建（选 A）**，并且用"守卫跑完 tests/ 一个字节都没动"来证明它绕开了那份 docstring 担心的风险 |

---

## 1. 存在性证明：全仓有多少条活的恒真断言

⚠️ **扫描范围要选对。** 第一次扫 `rglob('test_*.py')` 得到 **180 条**，
其中 177 条来自 `liaozhai_demo/acestep-env/`（一个 vendored venv）。
**在错误的尺度上测等于没测。** 限定到本项目 `tests/`：

```
TOTAL flagged assert lines: 3
tests/test_p46_probe_instruments.py:229  [OR_TRUE]  chart.unavailable(...) is None or True
tests/test_pipeline_validates_the_schema.py:332  [SELF_CMP]  sg.schema() is sg.schema()
tests/test_visual_qa.py:771  [OR_TRUE]  raw.decode('utf-8').isprintable() or True
```

⚠️ **第三条工单没有提到。** `test_pipeline_validates_the_schema.py:332`
是 C1 判据的**实测假阳性** —— `sg.schema` 是 `lru_cache` 的，
两次调用返回同一对象**就是被断言的性质**。§3 的合并决策直接由它决定。

修完两条活断言后重扫：`tests/` 下 **0 条**。

---

## 2. 覆盖矩阵（实测，非引述）

⚠️ 矩阵里的每一列都是**从真实文件里按 AST 节点位置切出来的源码原文**执行的，
不是复述。四段切片的 sha256 都打印在 `matrix.py` 的输出里，
所以"测的是哪几个字节"可核对。

```
ID   truth  C1 locked  C2 p42   C3 p27   C4 p46   shape
S01  TAUT   FLAG       FLAG     FLAG     n/a      assert True
S02  TAUT   FLAG       FLAG     FLAG     n/a      assert True or X
S03  TAUT   FLAG       FLAG     -        n/a      assert X or True
S04  TAUT   FLAG       FLAG     -        n/a      assert X or Y or True
S05  TAUT   -          FLAG     -        n/a      assert (X or True) and Y
S06  TAUT   FLAG       -        -        n/a      assert X == X
S07  TAUT   -          -        -        n/a      assert not False
S08  TAUT   FLAG       -        -        n/a      assert 1
S09  TAUT   -          -        -        n/a      assert X and False
S10  TAUT   -          -        -        n/a      assert X or not X
S11  TAUT   FLAG       -        -        n/a      assert f() == f()
S12  TAUT   FLAG       FLAG     -        n/a      assert X is None or True
S13  legit  -          -        -        n/a      assert a or b
S14  legit  -          -        -        n/a      assert X == Y
S15  TAUT   FLAG       FLAG     -        n/a      assert X > 0 or True
S16  legit  -          -        -        n/a      assert X is not None
S17  TAUT   -          -        -        n/a      assert True if X else Y
S18  TAUT   -          -        -        n/a      assert X is None or X is not None
S19  TAUT   FLAG       -        -        n/a      assert f() != f()
S20  legit  -          -        -        n/a      assert len(xs) == 0 or "skip" in msg

  C3 <= C1   (proper subset)
  C3 <= C2   (proper subset)
  union of C1,C2,C3 : S01 S02 S03 S04 S05 S06 S08 S11 S12 S15 S19
  MISSED by all     : S07, S09, S10, S17, S18
  FALSE POSITIVES   : []
```

**要点：**
- **C1 与 C2 互不可比**（无一是另一的子集）—— 指挥窗口的判断实测成立。
- **C3 是 C1 和 C2 的严格子集** —— 合并 C27 不会丢任何东西。
- 三个判据**误报率都是 0**（在 5 个合法形状上）。
- 三个都漏掉的 5 个形状里，`S09`（恒**假**）是另一类故障，会响亮地失败，不在"断言什么都没说"的范围内。

---

## 3. 合并决策：合两份，不合第三份

### 并集会让谁变红？—— **实测：谁都不会**

```
tests/test_locked_fields_wiring.py                          TOTAL 0
tests/test_p42_fade_is_not_a_freeze.py                      TOTAL 0
tests/test_p27_visual_acceptance_is_repeatable.py           TOTAL 0
```

⚠️ **这与工单的预期相反，工单问"会让另外两个文件的测试变红吗"——
实测是零。** 如实记录：那条预期不成立。

### 但 C1 还有第二层问题：它的作用域只有自己文件的 55%

```
_CONTRACT_TESTS names        : 11 个具名 contract test
asserts in the WHOLE file    : 29
asserts inside those fns only: 16
=> C1 INSPECTS 16/29 = 55% of this file's assertions
```

**C1 不是一条全仓判据**，它是一条"这个具名函数是不是整体空转"的判据。

### 所以最终决定

| | 做法 | 依据 |
|---|---|---|
| C3 (p27) | **合并到共享判据** | 实测是 C2 的严格子集，零损失 |
| C2 (p42) | **成为共享判据的宿主** | 已是最强的一份 |
| C1 (locked) | **不合。保留原样，写清为什么** | 覆盖面不可比 + 有实测假阳性 + 作用域不同 |
| C4 (p46) | **本来就没有**，现在通过共享判据获得一条 | — |

⚠️ **`test_locked_fields_wiring.py` 一个字节都没改。** 工单要求"改动前先说明为什么必须改"——
**我的结论是不必须改**，所以没改。

**关于那个假阳性：** `X == X`（写错了）和 `f() is f()`（在测缓存）
**在语法上是同一棵树**，没有可靠的办法分开。任何为了这一个样本凑出来的启发式，
都会带来一个没测过的盲区 —— 而那个盲区就是本项的起因。所以这条能力
**留在 `test_locked_fields_wiring.py`**，在那里它的假阳性不成立。

代价是明码标价的：`S06 / S11 / S19` 三个形状**只有 C1 覆盖**，
并集判据不覆盖。`test_the_three_shapes_only_the_locked_fields_rule_caught`
把这个缺口**钉成一条会红的断言**，缺口一旦被无意补上或扩大都会被发现。

---

## 4. 两条活的恒真断言

### `:229` —— **I（笔误）**，而且顺带丢了半条断言

```python
assert chart.unavailable(tmp_path / 'nope.png', transport=lambda *a: {}) is None or True
```

实测：

```
RETURN VALUE        : 'frame nope.png does not exist'
`X is None`         : False        ← 所以这条恒红，`or True` 压绿
`X is not None`     : True
transport 调用次数  : 0
```

`is None` 与它上面的 226/227 行（都是 `is not None`）、以及注释
（"a missing frame is **UNAVAILABLE**"）**都相反**。是漏了一个 `not`。

⚠️ **更深一层：注释的后半句"before any socket is opened"从来没被断言过。**
`transport=lambda *a: {}` 会把调用吞掉 —— 就算真开了 socket，这条也照样绿。
修的时候把 transport 换成会抛异常的，才让这半句变成真的。

修复后的断言**实测有牙**：

```
unmutated (real code)                  -> GREEN
MUTANT: missing frame -> None          -> RED   must report UNAVAILABLE with a reason
MUTANT: opens the socket first         -> RED   opened a socket for a missing frame
```

### `:771` —— **III（意图有意义，判据写错），而且实测完全冗余**

```python
assert raw.decode('utf-8').isprintable() or True   # decodable is the assertion
```

工单怀疑它冗余，**实测确认，而且比"冗余"更糟**：

```
A. isprintable() 在真实输出上是   : False      （控制字符 '\x0a' '\x0d'）
B. 字节不可解码时哪一行先红       : 769 行 json.loads 抛 UnicodeDecodeError
   => 执行根本走不到 771 行
C. `X or True` 对所有输入都 PASS，包括走不到的那一个
```

三件事同时成立：
1. **`isprintable()` 不是"decodable"。** JSON 跨行打印必然含换行 ⇒ 必假。
   作者写了检查 → 红了 → 加 `or True`。这**不是忘了写检查**。
2. **`:769` 已经 `json.loads(raw.decode('utf-8'))`** —— 不可解码会先在那里炸，
   `:771` **不可达**。
3. 所以这一行**信息量为零**：它声称的那个性质上一行已经断言过了。

⚠️ **但直接删掉会丢掉 docstring 记的那类真 bug。**
`--json` 的历史故障是 `ensure_ascii=False` 把真 CJK 穿过 GBK stdout
—— 那是 **mojibake**。所以不是删，是**换成一条真的判据**：
`U+FFFD not in text`。它今天绿（实测 0 个），而 769 抓不到的正是
"替换字符"这种**能解码、所以对 769 隐形**的情况。

```
real --json output                     -> GREEN
MUTANT: U+FFFD present                 -> RED   U+FFFD replacement character in --json
```

---

## 5. 守卫该不该建：**选 A**

`test_locked_fields_wiring.py` 拒绝造守卫的守卫，理由有二。逐条回应：

**理由一 —— "a test rewriting its own source: six silent CRLF patch failures,
and one `git checkout --` that discarded uncommitted work"。**

⚠️ 这条说的是**测试在运行时改写自己的源文件**。本方案不碰那个动作：
判据是 `ast` 树的**纯函数**，守卫的测试喂的是**字符串字面量**解析出来的夹具树。

⚠️ **但"我认为它不会写文件"不算论证。所以这条是量出来的**：
`test_this_guard_writes_nothing_to_disk` 在整轮扫描**前后**
对 `tests/` 下每个 `.py` 做 sha256，有任何一个字节动了就红。

**理由二 —— "Weakening the checks above leaves the suite fully green."**

⚠️ 这不是反对测判据的理由，**这正是要建守卫的理由**：
P50 把其中一份判据收窄成了 `values[0]`。
**一份判据有三个副本，就是它能在没人察觉的情况下被收窄的原因。**
现在判据只剩一份，且被一张形状表钉住。

**选 B 等于什么**：等于本项目承认"判据可以被静默收窄而无人发现" ——
而本项的起因恰恰是有人收窄了它。工单这一条是对的。

### 三条毒变异（全部贴 `-rf`，全部从字节快照复原）

| 变异 | 结果 |
|---|---|
| M1 把 `is_neutered` 改回只查 `values[0]`（P50 的缺陷形态） | **3 failed**，含 `test_the_criterion_is_not_the_p27_half_of_it` |
| M2 在测试文件里插入 `assert True or True` | **1 failed**：`test_no_assertion_in_this_repository_asserts_nothing` |
| M3 让 `offenders()` 永远返回"无违规" | **4 failed**，含 `test_the_criterion_flags_every_shape_it_claims_to` |

```
restore tautology_criterion.py       sha aa12cec58a02adc2 -> aa12cec58a02adc2 OK  CRLF=0
restore test_tautology_criterion.py  sha 3621f8628eb31dff -> 3621f8628eb31dff OK  CRLF=0
  all mutations red for the right reason: True
```

⚠️ **变异打在谁身上**：M1/M3 只碰 `tests/tautology_criterion.py`，
M2 只碰 `tests/test_tautology_criterion.py` —— **两个都是本项几分钟前新建的文件**。
**没有在任何人正在编辑的文件上做字节级改写**，
也没有用 `git checkout --`（工单第四节点名的那个错误）。

⚠️ **"红在错误的理由上"不算通过** —— 所以每条变异都额外断言了失败信息里
出现的是它**应该**给出的理由（`'X or True'` / `'assert nothing'` /
`'stopped flagging'`），三条全中。

---

## 6. 交付物

| 文件 | 改了什么 |
|---|---|
| `tests/tautology_criterion.py` | **新增**。唯一的判据，四条具名规则 |
| `tests/test_tautology_criterion.py` | **新增**。守卫的守卫 + 全仓扫描 + "守卫不写盘"证明 |
| `tests/test_p46_probe_instruments.py` | `:229` 修成真断言（I），并补上从未被断言的"不开 socket" |
| `tests/test_visual_qa.py` | `:771` 换成 U+FFFD 判据（III），不再是恒真 |
| `tests/test_p27_visual_acceptance_is_repeatable.py` | 判据委托到共享模块（实测严格更强） |
| `tests/test_p42_fade_is_not_a_freeze.py` | `_tautology_offenders` 委托（其自带元守卫照常跑同一份代码） |
| `tests/test_locked_fields_wiring.py` | **未改动** —— 结论是"不必改" |

⚠️ 账本 `docs/UPGRADE_PROGRESS.md` **未动**，由指挥窗口统一更新。