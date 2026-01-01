import logging
import sys
from .mcp_handler import mcp

# Stdioモードでは、標準出力(stdout)はMCPの通信専用になります。
# そのため、ログは全て標準エラー出力(stderr)に出す必要があります。
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # 重要: stderrに出力する
)

if __name__ == "__main__":
    # transportを指定しない場合、デフォルトでstdioモードになります
    mcp.run()