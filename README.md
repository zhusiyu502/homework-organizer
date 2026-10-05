# homework-organizer

批量作业文件整理脚本，分 3 个迭代 PR 实现。

仅使用 Python 标准库，兼容 Windows。

## 功能

### 需求1：扫描与列出文件（只读）

- 接收目标文件夹路径，遍历其内文件（不递归子文件夹）
- 输出表格：文件名 | 文件大小(KB) | 文件修改时间
- 支持 `--ext` 按后缀过滤，例如只扫描 `.docx,.pdf`

### 需求2：按文件类型自动归档（`--organize`）

- 按后缀分类并移动到 `图片 / 文档 / 视频 / 其他` 文件夹：

  | 分类 | 后缀 |
  | ---- | ---- |
  | 图片 | jpg, jpeg, png, gif, bmp |
  | 文档 | pdf, docx, doc, txt, xlsx |
  | 视频 | mp4, mov, avi |
  | 其他 | 其余所有后缀 |

- 只移动文件，不移动子文件夹；分类文件夹不存在时自动创建
- `--dry-run` 模拟移动：只打印操作日志，**不改动任何本地文件**（安全预览）
- 复用需求1的 `collect_files()` 扫描逻辑
- 真实归档前给出警告并二次确认，输入 `y` 才继续，其他输入直接取消
- 同名文件自动追加序号（如 `a_1.txt`），绝不覆盖已有文件
- 归档结束（含 dry-run）后输出各分类数量汇总

## 使用方法

```bat
REM 1) 扫描当前目录并列出文件
python homework_organizer.py .

REM 2) 只扫描指定后缀
python homework_organizer.py . --ext .docx,.pdf

REM 3) 先模拟归档，安全预览（推荐）
python homework_organizer.py "D:\作业" --organize --dry-run

REM 4) 确认无误后真正归档（执行前会二次确认）
python homework_organizer.py "D:\作业" --organize

REM 5) 只归档指定后缀
python homework_organizer.py "D:\作业" --organize -e pdf,docx --dry-run

REM 6) 查看帮助
python homework_organizer.py -h
```

## 运行测试

项目附带基于标准库 `unittest` 的单元测试，无需第三方依赖：

```bat
python -m unittest -v
```

测试覆盖分类规则、扫描（跳过子文件夹/后缀过滤）、dry-run 不改变磁盘、真实移动与自动建目录、同名文件不覆盖，以及命令行的确认/取消流程。
