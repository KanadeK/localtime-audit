# localtime-audit 中文说明

审计 CSV 中没有 UTC 偏移的本地时钟时间：输出唯一、重复、不存在或无效的分类；重复时刻列出两个按 UTC 先后排序的候选，不自动选一个，也不把不存在的时间静默平移。

Python 3.10+，本地处理，唯一运行时依赖为时区数据包 tzdata。安装：在独立虚拟环境执行 `python -m pip install .`。

```sh
localtime-audit examples/clocks.csv --column local_time --zone-column zone --output audit.csv --format json
localtime-audit examples/unique.csv --column local_time --zone Asia/Shanghai --output unique-audit.csv
```

第一个示例有 4 条记录：2 条唯一、1 条重复、1 条不存在，完整报告生成后返回 1。这是预期质量检查结果。第二个示例全部唯一，返回 0。输出已存在时拒绝覆盖，原文件保持不变。这里只提供源码/GitHub 安装包，不声称已发布 PyPI。

时间格式为 `YYYY-MM-DD HH:MM[:SS[.ffffff]]`，也可使用大写 `T` 分隔，精度最多微秒。带 `Z` 或 UTC 偏移的输入会标记为无效，因为本工具审计的是未确定 UTC 的墙钟时间。必须指定一个固定 IANA 时区，或者指定每行的时区列；不猜测系统时区。

结果保留原字段，增加记录号、物理行号、分类/原因、两个 UTC 候选、对应偏移和 tzdata/IANA 版本。统一从已安装的 tzdata 数据读取规则，避免宿主系统数据库差异。支持半小时变更及整天跳过，不能推断用户原本想表达哪个重复时刻。

默认 UTF-8（允许 BOM）；旧编码可显式使用 `--encoding cp1252`。分隔符支持 `--delimiter comma|tab|semicolon`。输入实际读取上限 64 MiB，默认最多 100 万条记录，单字段还受 Python csv 默认大小限制。格式错误、重复表头和已有审计列会拒绝处理。

退出码：0=全部唯一，1=报告中含重复/不存在/无效记录，2=参数、格式、配置或 IO 失败。返回 1 仍会生成完整报告；格式失败不发布半份报告。新报告通过硬链接原子创建，目标文件系统需支持硬链接；FAT/exFAT 或部分网络文件系统可改用本地 NTFS/APFS/ext4 目录生成后再复制。

处理时不联网。报告复制原数据，分享前检查隐私。时区规则可能更新，重要结果应保留规则版本。卸载：`python -m pip uninstall localtime-audit`；退出后删除独立虚拟环境即可连同依赖一起清理。原始代码 MIT，tzdata 保留其上游许可，详见 [THIRD_PARTY.md](THIRD_PARTY.md) 和 [英文文档](README.md)。
