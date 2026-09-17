"""
系统检查脚本 - 验证环境配置是否正确
"""

import sys
import os
from pathlib import Path

# 设置 UTF-8 输出编码（Windows 兼容）
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, errors="replace")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, errors="replace")


def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    if (version.major, version.minor) >= (3, 9):
        print(f"✓ Python 版本: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python 版本过低: {version.major}.{version.minor}.{version.micro}")
        print("  需要 Python 3.9 或更高版本")
        return False


def check_dependencies():
    """检查依赖是否安装"""
    required = [
        "volcenginesdkarkruntime",
        "flask",
        "PIL",
        "requests",
        "dotenv",
    ]

    all_ok = True
    for module in required:
        try:
            __import__(module)
            print(f"✓ {module} 已安装")
        except ImportError:
            print(f"✗ {module} 未安装")
            all_ok = False

    return all_ok


def check_api_key():
    """检查 API Key 是否配置"""
    api_key = os.environ.get("ARK_API_KEY")

    if api_key:
        print(f"✓ API Key 已配置: {api_key[:8]}...")
        return True
    else:
        # 检查 .env 文件
        env_file = Path(".env")
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("ARK_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        if key and key != "your_api_key_here":
                            print(f"✓ API Key 在 .env 文件中: {key[:8]}...")
                            print("  (需要运行时加载 .env 文件)")
                            return True

        print("✗ API Key 未配置")
        print("  请设置环境变量 ARK_API_KEY 或在 .env 文件中配置")
        return False


def check_client():
    """检查客户端是否可以初始化"""
    try:
        # 临时设置 API key 如果 .env 存在
        env_file = Path(".env")
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("ARK_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        if key and key != "your_api_key_here":
                            os.environ["ARK_API_KEY"] = key

        from imageto3d.client import Seed3DClient
        client = Seed3DClient()
        print("✓ Seed3DClient 初始化成功")
        return True
    except Exception as e:
        print(f"✗ Seed3DClient 初始化失败: {e}")
        return False


def check_cli():
    """检查命令行工具是否可用"""
    try:
        import subprocess
        result = subprocess.run(
            ["imageto3d", "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✓ 命令行工具 'imageto3d' 可用")
            return True
        else:
            print("✗ 命令行工具执行失败")
            return False
    except FileNotFoundError:
        print("✗ 命令行工具 'imageto3d' 未找到")
        print("  请运行: pip install -e .")
        return False
    except Exception as e:
        print(f"✗ 检查命令行工具时出错: {e}")
        return False


def check_directories():
    """检查必要的目录"""
    dirs = ["imageto3d", "examples", "tests"]
    all_ok = True

    for dir_name in dirs:
        if Path(dir_name).exists():
            print(f"✓ 目录存在: {dir_name}/")
        else:
            print(f"✗ 目录不存在: {dir_name}/")
            all_ok = False

    return all_ok


def check_files():
    """检查关键文件"""
    files = [
        "pyproject.toml",
        "README.md",
        "GUIDE.md",
        ".env.example",
        "imageto3d/__init__.py",
        "imageto3d/client.py",
        "imageto3d/cli.py",
        "imageto3d/web.py",
        "imageto3d/templates/index.html"
    ]

    all_ok = True
    for file_name in files:
        if Path(file_name).exists():
            print(f"✓ 文件存在: {file_name}")
        else:
            print(f"✗ 文件不存在: {file_name}")
            all_ok = False

    return all_ok


def main():
    """运行所有检查"""
    print("=" * 60)
    print("Image to 3D - 系统检查")
    print("=" * 60)
    print()

    checks = [
        ("Python 版本", check_python_version),
        ("项目目录", check_directories),
        ("项目文件", check_files),
        ("依赖包", check_dependencies),
        ("API Key", check_api_key),
        ("客户端", check_client),
        ("命令行工具", check_cli),
    ]

    results = []
    for name, check_func in checks:
        print(f"\n检查 {name}:")
        print("-" * 40)
        result = check_func()
        results.append((name, result))
        print()

    # 输出总结
    print("=" * 60)
    print("检查结果总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status} - {name}")

    print()
    print(f"总计: {passed}/{total} 项检查通过")
    print()

    if passed == total:
        print("🎉 所有检查通过！系统配置正确。")
        print()
        print("快速开始:")
        print("  1. Web 界面: start_web.bat  (或 ./start_web.sh)")
        print("  2. 命令行: imageto3d create --image-url <url>")
        print("  3. Python: python examples/quickstart.py")
        return 0
    else:
        print("⚠️  存在配置问题，请根据上述提示修复。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
