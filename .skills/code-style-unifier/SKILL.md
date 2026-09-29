---
name: code-style-unifier
description: |
  统一代码风格。当用户生成、改善或适配代码时，自动应用中文 docstring 和统一的编码风格。
  此 skill 只在 JustOne 项目中使用，确保所有代码风格与 common/ 目录一致。
---

# Code Style Unifier

当用户要求生成、改善或适配代码时，自动应用统一的代码风格。

## 触发条件

以下任一情况触发：
- 用户要求生成新代码
- 用户要求改善代码
- 用户要求适配代码
- 用户提到"统一风格"、"风格统一"

## 统一风格规范

### 1. 模块 docstring 格式

```python
"""
模块名称

模块功能描述...
"""
```

### 2. 函数/方法 docstring 格式

使用中文描述，包含：
- 功能说明
- 参数说明（使用 `:param` 格式）
- 返回值说明（使用 `:return` 格式）

```python
def function_name(param1, param2):
    """
    函数功能描述

    :param param1: 参数1描述
    :param param2: 参数2描述
    :return: 返回值描述
    """
```

### 3. 类 docstring 格式

```python
class ClassName:
    """类功能描述"""

    def __init__(self, params):
        """
        初始化方法

        :param params: 参数描述
        """
```

### 4. 导入顺序

1. 标准库（os, re, time, json, etc.）
2. 第三方库（requests, dns.resolver, etc.）
3. 本项目模块（from common import xxx）

### 5. 变量/函数命名

- 函数/方法：小写下划线（snake_case）
- 类名：大驼峰（PascalCase）
- 常量：全大写下划线（SNAKE_CASE）

### 6. 日志输出

使用中文描述：
```python
logger.debug('正在执行某操作')
logger.info('操作完成')
logger.warning('警告信息')
logger.error('错误信息')
```

## 执行步骤

### Step 1: 分析目标文件

读取目标文件，分析需要修改的部分。

### Step 2: 应用风格规范

1. 更新模块 docstring 为中文
2. 更新类和函数的 docstring 为中文
3. 确保导入顺序正确
4. 添加必要的中文注释

### Step 3: 运行测试

使用 `python -m unittest tests.test_<模块名>` 运行测试，确保修改没有引入 bug。

### Step 4: 报告结果

告诉用户修改的内容和测试结果。

## 示例

用户输入："为 xxx 模块改善代码"

输出：
1. 读取 xxx.py 文件
2. 更新 docstring 为中文
3. 更新函数说明为中文
4. 运行测试
5. 报告结果