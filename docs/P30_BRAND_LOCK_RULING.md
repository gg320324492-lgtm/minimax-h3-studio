# P30 — 把品牌锁接上：(a)(b)(c) 的裁定与依据

> 执行 agent 交付。**本文件记录裁定，不是放行裁定。**
> 三条变异与实测输出见 §七；测试与 sha256 见 §八。

---

## 一、动手前的实测（不是引述）

指挥窗口的复现我在本地重跑了一遍，全部一致：

| 动作 | P30 之前 | P30 之后 |
|---|---|---|
| 改 logo 场景的 `content.name`（"MERIDIAN"→"ACME"） | **0 条违规** | 1 条，`brand` |
| 把 logo 改道成 `bar-chart` | **0 条违规** | 1 条，`brand` |
| 删掉整个 logo 场景 | **0 条违规** | 1 条，`brand` |
| `coverage_report(...).by_kind.brand` | **`[]`** | `['name', 'type']` |

⚠️ 我比工单多测了一条，因为工单的三条里没有它而它显然该被问：
**`pipeline/examples/*.json` 两个图谱里一个 `logo` 场景都没有。**
所以 `brand` 那一类过去不是"命中数为零"，是**根本没有可命中的东西**——
`by_kind.brand == []` 与"锁生效但没人用"在数据上无法区分。这一点决定了 (c) 的做法（§五）。

---

## 二、(a) 锁什么

**裁定：锁两样，都限定在 `LOCKED_SCENE_TYPES` 之内。**

1. **`scene.type`** —— 品牌场景不许被改道。
2. **`scene.content.name`** —— 字标（wordmark）不许被改、被删、被凭空补出来。

### 为什么不止锁 `type`

只锁 `type`，"MERIDIAN" 改成 "ACME" 畅通无阻。那这把锁挡住了一次改道，放过了同一种谎的下一个形态。

依据不是我的口味，是这个模块**自己已经写死的边界**，以及它自己最锋利的那条测试：

- `locked_fields.py` 模块 docstring：*"you may move how a number is presented, never what it says."*
- `test_a_repair_may_not_shorten_labels` 的失败说明：*"Shortening labels is the only lever that can clear a chart collision, and it is a lie: the axis labels are the data. This is the whole task in one test."*

把字标改短或换掉来腾地方，正是那同一个动作的品牌版。工单自己的表格问「品牌锁是否也要禁改名」——**要禁，而且理由与 `labels` 那条完全同构**。

`type` 那一条的依据同样不是推测，是这个常量旁边的注释和 `Brand.tsx:19-20` 引用它的原话：
*"Locking the type is what stops a repair from rerouting it to a chart to make it fit."*

### ⚠️ 为什么**不能**把 `name` 塞进 `LOCK_RULES`（这一条是本次实现里最关键的形状判断）

`LOCK_RULES` 靠 `_RULES_BY_KEY.get(leaf)` **在每一个场景里**按键名匹配。
若写成 `LockRule('name', 'brand', ...)`，锁的是**所有**场景的 `content.name`。

实测：现有全部图谱里 `content.name` 只出现在 `logo` 与 `outro` 上，别的场景类型都没有。
**但这不是保证**：`content` 是 `z.record(z.string(), z.unknown())`（`showcase-v1.ts:256`），
没有任何东西能阻止将来某个场景带一个叫 `name` 的、并非品牌的字段（商品名、人名）。

**⇒ 也就是说，把品牌锁写进 `LOCK_RULES`，恰好会制造工单第三条变异要抓的"过度锁"。**
所以品牌锁走一条**按场景类型限定**的独立通道：`LOCKED_SCENE_TYPES` + `BRAND_CONTENT_KEYS`。
守卫 `test_a_non_brand_scene_may_carry_its_own_name` 专门钉住这个判断。

### 为什么走"现有返回路径"

工单要求不得另起一套机制（P21 的教训：两个调用点一个用常量一个硬编码字面量）。
实现方式：`iter_scene_locked()` 产出**与 `iter_locked` 完全相同的 5 元组**，
`diff_locked` 把两条通道喂给**同一个 `emit()`**。所以：

- 返回类型仍是 `LockedField`，`kind` 仍是既有三种之一；
- `main()` 的输出格式、`diff_locked` 的双向对称性、删除即违规的语义，全部原样成立；
- **没有第二个返回路径**可供调用方忘记检查。

两条通道各持一份 `seen` 集合，这是有意的：`_anchor()` 让内容路径按叶子键、
场景级路径按整条路径锚定，否则 `content.chart.type` 与场景自身的 `type`
会在同一索引上撞锚，**后走的那条 finding 被静默丢弃**——锁因为内部缓存丢结论，
和锁没写一样。

---

## 三、(b) 锁到多严

**裁定：与其它 14 条一样，编辑 / 删除 / 新增全部算违规。不为品牌开特例。**

明确**不锁**的边界：

| 不锁 | 理由 |
|---|---|
| `durationInFrames` / `camera` / `motion` / `style_bible` / `layout` / `transitionIn` / `transitionOut` / `format` | 11.1 点名的合法杠杆，**即使在 `logo` 场景上也放行**。守卫有 8 条参数化测试逐个钉住 |
| `content.tagline` | `Brand.tsx:33-37` 自称 lockup 是 MARK + WORDMARK + *optionally* a TAGLINE。字标是身份，tagline 是"可选"。**但这是产品判断，见 §六 Q2** |
| `notes` / `id` | 图谱注释与标识，不是 claim |

---

## 四、`kind` 用哪个：不需要第四种

**`'brand'` 一直都在。** 它在 P11 就被预留了：写在 `LockRule.kind` 的注释里、
列在 `coverage_report()` 的 `('fact','copy','brand','identity')` 元组里、
被接线守卫列进允许集合——**只是从来没有任何一条规则用它**。

这正是账本只能报出「fact 9 / copy 4 / identity 1」而账本自己写的是三个名词的原因：
桶建好了，从来没往里放过东西。**本次是往已有的桶里填，不是新建桶。**

对既有守卫的影响：`test_locked_fields_wiring.py` 里
`kinds <= {'fact','copy','brand','identity'}` 这条**继续成立且不受影响**，
因为我是往已声明的集合里填。

---

## 五、(c) `by_kind` 与 `unexercised` 的影响

| | 之前 | 之后 |
|---|---|---|
| `by_kind['brand']` | `[]` | `['name', 'type']` |
| `by_kind['fact'/'copy'/'identity']` | 9 / 4 / 1 | **不变** |
| `rules` | 14 | **14，不变** |
| `unexercised`（对 `pipeline/examples`） | `[]` | **`[]`，不变** |
| `scene_locks`（新增小节） | 不存在 | 对 examples：`unexercised: ['logo','name']`；对 p29 图谱：`unexercised: []` |

### ⚠️ 为什么**没有**把品牌锁并进 `unexercised`

`unexercised` 现在的含义是「没有图谱命中的 `LOCK_RULES` 键」，
它被 `test_every_rule_is_exercised_by_the_shipped_graphs` 断言，
账本也把它记成 `[]` 并称"零盲区"。**悄悄改掉一个别处已经引用的数字的含义，
和当初那条不兑现的注释是同一类错。**

但并进去的代价也很实在：品牌锁不在 `LOCK_RULES` 里，若不单独统计，
它在 `coverage_report()` 里就是**完全隐形**的——而这个函数存在的唯一目的
就是让盲区可见（模块 docstring 原话）。

⇒ 所以新增 `scene_locks` 小节，沿用同一套 exercised/unexercised 词汇。
**盲区从"沉默"变成"写在报表上"**：examples 里它诚实地报 `['logo','name']`，
因为那两个图谱确实没有品牌场景。

> 实现中我踩过一次自己的坑并修掉：`scene_locks` 最初把场景**类型**按规则键 `'type'` 计数，
> 却拿它和类型**名** `'logo'` 比对，于是**每个**图谱都把 logo 报成未覆盖。
> 探针跑出来才发现。类型现在按名字统计。

---

## 六、⚠️ 我**没有**替指挥/用户拍板的两件事

这两条我**实现了机制但没有决定取值**，因为它们会改变锁的覆盖范围，
而账本与这个常量都没说过。它们写在 `locked_fields.py` 里
`WHAT A READER STILL HAS TO DECIDE` 一节（不是只写在文档里），
并由 `test_the_ruling_about_what_counts_as_brand_is_still_recorded_in_the_source` 钉住那段记录还在。

### Q1：`outro` 算不算品牌场景？

**实测**：`p29_new_renderer_showcase.json` 的 `outro` 场景带 `content.name`，
`Brand.tsx:156-157` 用**同一个 `Lockup` 组件**把它渲染出来
（`Logo` 在 `:122-123` 读的是同一对键）。
所以**字标在 outro 上是会被看见的**，而今天改 outro 的字标**不受任何阻拦**——这是可演示的绕过。

**我不加它的理由**：账本写的是「品牌 logo」，这个常量从 P11 起就是 `{'logo'}`。
把 `{'logo'}` 变成 `{'logo','outro'}` 是把锁从"logo 这个场景"扩成"品牌出现在哪都锁"，
这是产品决定，不是实现细节。

**代价对比**：
- 不加：一个只改 outro 字标的修复可以溜过去。
- 加：**改一个词**（`'logo'` → `'logo', 'outro'`），本文件的守卫全部继续成立，
  且 `test_the_lock_follows_the_set_it_is_given` 立刻开始覆盖它。

### Q2：`content.tagline` 锁不锁？

**实测**：字标是身份，tagline 是 `Brand.tsx` 自己称作 "optionally" 的那部分。
**不加的理由**：账本没点名它，且它不是 mark 本身。
**代价对比**：不锁则品牌定位语可被改写；锁则覆盖范围比"mark"更宽。

**机制已经就位**：加进 `BRAND_CONTENT_KEYS` 就是全部改动，守卫自动跟随
（`test_the_brand_content_keys_are_read_too` 就是为此写的）。

---

## 七、三条变异（外加两条），原始 `-rf` 输出

守卫文件：`tests/test_brand_lock_wiring.py`（30 条）。
变异脚本：`_p30_mutation_run.py`。

> ⚠️ 脚本里有一个**探针**，在跑测试之前先测锁的可观测行为。
> 起因：M2 第一版我写成 `if False: return`，**字节确实写进了文件、pytest 全绿**——
> 看起来像"守卫漏了一个真变异"，其实是那个分支根本不执行、变异是死的。
> **字节落地 ≠ 行为改变。** 现在探针不动就报 `INERT`，绝不报"存活"。

### 基线探针

```
{"brand_rename": 1, "brand_reroute": 1, "brand_scene_deleted": 1,
 "chart_gets_a_name": 0, "identity_diff": 0, "lever_on_brand": 0, "nonbrand_reroute": 0}
```

### M1 —— 品牌规则从 `diff_locked` 里摘掉（= 今天的状态）

```
== M1_brand_rule_absent_from_diff_locked: bytes landed (-51), anchor was b'    scene_seen: set[tuple[int, str, str]] = set('
FAILED ::test_an_attack_on_the_brand_is_caught[delete the wordmark]
FAILED ::test_an_attack_on_the_brand_is_caught[rename the wordmark]
FAILED ::test_an_attack_on_the_brand_is_caught[reroute the brand scene to a chart]
FAILED ::test_an_attack_on_the_brand_is_caught[reroute the brand scene to another brand-shaped scene]
FAILED ::test_inventing_a_wordmark_where_there_was_none_is_caught
FAILED ::test_deleting_the_brand_scene_entirely_is_caught
FAILED ::test_a_non_brand_scene_may_carry_its_own_name
FAILED ::test_the_lock_follows_the_set_it_is_given
FAILED ::test_the_brand_content_keys_are_read_too
FAILED ::test_the_three_kinds_from_the_ledger_are_all_present
FAILED ::test_the_module_under_test_still_declares_what_the_contract_assumptions
11 failed, 59 passed in 5.76s
== restored locked_fields.py: sha256 8395291cd3c8d514 MATCHES entry snapshot
```

**存活判定：杀死。** 最后两条是**原来那三条只断言常量的旧守卫**——
它们在 P30 之前对 M1 是绿的，现在红了。这就是"守卫从断言名字改成断言行为"的直接证据。

### M2 —— 规则永远不 emit（调用点在，walker 哑了）

```
== M2_rule_never_emits: bytes landed (+23)
== probe: {"brand_rename": 0, "brand_reroute": 0, "brand_scene_deleted": 0, ...}
== probe moved vs baseline -> the mutation is live, result below is real
FAILED ::test_an_attack_on_the_brand_is_caught[delete the wordmark]
FAILED ::test_an_attack_on_the_brand_is_caught[rename the wordmark]
FAILED ::test_an_attack_on_the_brand_is_caught[reroute the brand scene to a chart]
FAILED ::test_an_attack_on_the_brand_is_caught[reroute the brand scene to another brand-shaped scene]
FAILED ::test_inventing_a_wordmark_where_there_was_none_is_caught
FAILED ::test_deleting_the_brand_scene_entirely_is_caught
FAILED ::test_a_non_brand_scene_may_carry_its_own_name
FAILED ::test_the_lock_follows_the_set_it_is_given
FAILED ::test_the_brand_content_keys_are_read_too
FAILED ::test_the_brand_lock_is_visible_in_coverage
FAILED ::test_the_three_kinds_from_the_ledger_are_all_present
FAILED ::test_the_module_under_test_still_declares_what_the_contract_assumptions
12 failed, 58 passed in 7.20s
== restored locked_fields.py: sha256 8395291cd3c8d514 MATCHES entry snapshot
```

**存活判定：杀死。** 与 M1 分开跑是有意的：M1 杀调用点，M2 杀 walker。
只防住 M1 的守卫，加回两行 `emit` 就又绿了，而规则依然什么都产不出来。

### M3 —— ⚠️ 过度锁：规则对所有场景类型都 emit

> 工单写的 `if False:` 落在**过滤那一行**上时，产生的正是这一条：
> 把「不是品牌类型就跳过」变成永假，等于**取消**过滤，而不是关掉规则。

```
== M3_rule_emits_for_every_scene_type: bytes landed (+22)
== probe: {"brand_rename": 1, "brand_reroute": 1, "brand_scene_deleted": 3,
           "chart_gets_a_name": 1, "identity_diff": 0, "lever_on_brand": 0, "nonbrand_reroute": 1}
== probe moved vs baseline -> the mutation is live, result below is real
FAILED ::test_a_non_brand_scene_may_be_rerouted_freely
FAILED ::test_a_non_brand_scene_may_carry_its_own_name
FAILED ::test_the_lock_follows_the_set_it_is_given
FAILED ::test_the_brand_lock_is_visible_in_coverage
FAILED ::test_coverage_of_the_example_graphs_reports_the_brand_lock_as_unexercised
5 failed, 65 passed in 6.29s
== restored locked_fields.py: sha256 8395291cd3c8d514 MATCHES entry snapshot
```

**存活判定：杀死。而且这一条的数字最说明问题：`5 failed, 65 passed`。**

**§一里"锁住品牌了吗"那一整组测试全部是绿的。** 过度锁抓得更多，
所以它通过每一个"抓到了吗"的断言——**只有"非品牌仍然自由"那几条能看见它**。
工单坚持要写那两条非品牌断言，理由就在这个 `65 passed` 里。

### M4 —— 给 11.1 的合法杠杆加锁：**探针判定为 INERT，未计入存活**

```
== M4_lock_a_legitimate_lever: bytes landed (+78)
== probe: {... 与基线完全相同 ...}
!! M4_lock_a_legitimate_lever: INERT — behaviour identical to the unmutated baseline.
!! Not counting this as "survived"; the mutation needs rewriting.
```

**这不是我这条守卫的问题，是一个既有事实**（见 §九）。

### M5 —— 把整个品牌场景锁掉（验证杠杆守卫真有牙）

```
== M5_lock_the_whole_brand_scene: bytes landed (+1)
== probe: {"brand_rename": 2, "brand_reroute": 1, "brand_scene_deleted": 5,
           "chart_gets_a_name": 0, "identity_diff": 0, "lever_on_brand": 1, "nonbrand_reroute": 0}
== probe moved vs baseline -> the mutation is live, result below is real
FAILED ::test_the_11_1_levers_still_pass_on_a_brand_scene[camera.translateZ]
FAILED ::test_the_11_1_levers_still_pass_on_a_brand_scene[durationInFrames]
FAILED ::test_the_11_1_levers_still_pass_on_a_brand_scene[layout.padX]
FAILED ::test_the_11_1_levers_still_pass_on_a_brand_scene[motion]
FAILED ::test_the_11_1_levers_still_pass_on_a_brand_scene[notes]
FAILED ::test_the_11_1_levers_still_pass_on_a_brand_scene[style_bible]
FAILED ::test_the_11_1_levers_still_pass_on_a_brand_scene[transitionIn]
FAILED ::test_the_11_1_levers_still_pass_on_a_brand_scene[transitionOut]
FAILED ::test_the_brand_content_keys_are_read_too
FAILED ::test_the_brand_lock_is_visible_in_coverage
10 failed, 60 passed in 6.45s
== restored locked_fields.py: sha256 8395291cd3c8d514 MATCHES entry snapshot
```

**存活判定：杀死。8 条杠杆断言在 logo 场景上全部转红。**
工单要求"守卫必须同时断言这七个杠杆仍然放行"——这就是那条断言有牙的证据。

---

## 八、⚠️ 我的操作失误（如实记录）

1. **M2 第一版是死的。** 写成 `if False: return`，字节写进了文件、锚点也"落地"了、
   pytest 全绿。我差点把它报成"守卫漏了 M2"。是探针发现探针不动才识破的。
   **教训：断言"变异在文件里"只证明写入成功，不证明行为改变。**
   我第一版的协议正好是工单第三节第 1 条，而那条不够——它只查了落地。
2. **`coverage_report` 我第一版写错了命名空间**：场景类型按 `'type'` 计数却与 `'logo'` 比较，
   于是每个图谱都把 logo 报成未覆盖。是探针输出（p29 报 `unexercised: ['logo']`）发现的。
3. **一次 Edit 的 `old_string` 我打错了变量名**（`used_used`），工具直接拒绝，没有改坏文件。
4. **一次 Edit 的 `new_string` 里我留了半截废表达式**（`... if False else ...`），
   工具因匹配失败一并挡下。两次都是"工具报错"，不是"改了再回滚"。
5. **`test_brand_lock_wiring.py` 第一版里有一条不诚实的测试**：
   `'invent a wordmark where there was none'` 用的是和 `'rename the wordmark'` 完全相同的 mutator，
   名字承诺了它没测的东西。已删除，并另写了一条真测"凭空补字标"的
   `test_inventing_a_wordmark_where_there_was_none_is_caught`。
6. **M4 我判定为 INERT 而没有硬凑成"杀死"。** 理由见 §九。

---

## 九、⚠️ 顺带实测到的一个既有事实（不属本项，未改）

`iter_locked()` **只走 `scene['content']`**。而 11.1 的七个杠杆
（`durationInFrames` / `camera` / `motion` / `layout` / `style_bible` / `format` / `transitionIn/Out`）
**全部是场景顶层键**。实测：

```
content keys that are 11.1 levers: NONE
```

⇒ **一条以杠杆命名的 `LockRule` 在任何真实图谱上都不可能命中。**
所以 `locked_fields_mutation.py` 里既有的 `lock_a_legitimate_lever`
（加一条 `LockRule('durationInFrames', ...)`）**在行为上是死的**，
它只可能被 `test_the_lever_list_is_not_a_subset_of_the_lock` 这条**结构性**测试杀掉，
任何行为测试都看不见它。

**这不影响既有结论**（杠杆确实没被锁，`test_the_lever_list_is_not_a_subset_of_the_lock`
也确实抓得到它），但账本把它列为"4 个变异全杀"之一时，
读者会以为存在一条行为上的证据链，实际没有。**建议提请裁定，本项未改该文件。**

---

## 十、改动的文件

| 文件 | 改了什么 |
|---|---|
| `studio/scripts/locked_fields.py` | 新增 `iter_scene_locked` / `BRAND_CONTENT_KEYS`；`diff_locked` 两通道走同一 `emit()`；`_counterpart_path` 支持场景级路径；`_anchor` 分命名空间；`coverage_report` 加 `scene_locks` 并让 `by_kind['brand']` 非空；**删除了 `diff_locked` 里两个从未被使用的死变量** `b_by_path`/`a_by_path` |
| `tests/test_brand_lock_wiring.py` | **新增**，30 条，全部断言 `diff_locked` 的行为 |
| `tests/test_locked_fields.py` | `_brand_graph`/`_brand_scene_index` 两个 helper；`test_the_three_kinds_from_the_ledger_are_all_present` 的常量断言改为行为断言 |
| `tests/test_locked_fields_wiring.py` | `test_the_module_under_test_still_declares_what_the_contract_assumptions` 的 `assert 'logo' in LOCKED_SCENE_TYPES` 改为行为断言 |
| `_p30_mutation_run.py` | **新增**，变异脚本 + 行为探针（临时产物，已清理） |

**未触碰**：`visual_qa.py` / `frame_baseline.py`（sha256 与工单给定值一致）、
`Brand.tsx` 的实现、11.2 那 14 条 `LOCK_RULES`、`out/**`、`DiagOutputDir`、
`docs/UPGRADE_PROGRESS.md`、账本与 P1/P2 文档。

### ⚠️ 留给下一个人的两处过期注释（**本项未改，超出授权范围**）

- `Brand.tsx:15-29`：*"The lock itself is untouched; `tests/test_locked_fields.py` still pins it."*
  —— 两句现在都不成立了（锁被接线了，测试也改成断言行为了）。
- `Brand.tsx:29` 引用的 `showcase-v1.ts:36`，实际 `'logo'` 在 **:82**；
  `locked_fields.py` docstring 里的 `showcase-v1.ts:100`，实际 `content` 在 **:256**。
  （本项新增的注释我按实测写了正确行号。）
