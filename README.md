# dbotxkeeper
DBotX 跟单交易监护脚本

## 系统要求：

- Python 3.10+

## 使用教程

### 1. 安装项目

首先，克隆项目并安装所需的依赖包：

```bash
git clone https://github.com/fachebot/dbotxkeeper.git
cd dbotxkeeper
pip3 install -r requirements.txt
```

### 2. 初始化配置文件

复制示例配置文件以进行初始化：

```bash
cp config.json.sample config.json
```

然后编辑 `config.json` 文件填写自己的配置信息。

### 3. 运行脚本
```bash
python dbotxkeeper.py
```