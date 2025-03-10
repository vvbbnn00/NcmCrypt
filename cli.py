# cli.py
import argparse
import json
import os
from encryptor import NCMEncryptor


def main():
    """命令行接口主函数"""
    parser = argparse.ArgumentParser(
        description="NcmCrypt 是一个用于将普通音频文件加密为网易云音乐专用格式（.ncm）的工具。",
    )

    # 必选参数
    parser.add_argument("--file_path", required=True, help="输入音频文件的路径")
    parser.add_argument("--img_path", required=True, help="封面图片文件的路径")
    parser.add_argument("--meta_path", required=True, help="包含元数据的JSON文件路径")

    # 可选参数
    parser.add_argument("--key_data", default=None, help="自定义密钥数据，默认为内置密钥")
    parser.add_argument("--output", default="output.ncm", help="输出文件路径，默认为output.ncm")
    parser.add_argument("--debug", action="store_true", help="开启调试日志输出")

    args = parser.parse_args()

    # 验证输入文件存在
    if not os.path.exists(args.file_path):
        print(f"错误: 输入音频文件不存在: {args.file_path}")
        return 1

    if not os.path.exists(args.img_path):
        print(f"错误: 封面图片文件不存在: {args.img_path}")
        return 1

    # 读取元数据文件
    try:
        with open(args.meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except Exception as e:
        print(f"错误: 读取元数据文件失败: {e}")
        return 1

    # 创建输出目录（如果不存在）
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建输出目录: {output_dir}")

    # 初始化加密器并执行加密
    try:
        encryptor = NCMEncryptor(key_data=args.key_data, debug=args.debug)
        encryptor.encrypt(args.file_path, args.img_path, meta, args.output)
        print(f"加密成功！输出文件: {args.output}")
        return 0
    except Exception as e:
        print(f"加密失败: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
