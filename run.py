"""
Local Document Number Extractor
Main application runner.
"""
import uvicorn
import os
import sys

def main():
    print("=" * 60)
    print("Local Document Number Extractor - 100% Local Pipeline")
    print("=" * 60)
    # Ensure project root is in sys.path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
