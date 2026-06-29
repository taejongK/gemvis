#!/usr/bin/env python3
"""Gemvis entry point."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("gemvis.api:app", host="0.0.0.0", port=8000, reload=True)
