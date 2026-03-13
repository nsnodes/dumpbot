# Claude Code Guidelines for DumpBot

## Coding Philosophy

**Main point**: when writing python, I like code that leverages native python modules where appropriate and as such is truly pythonic and succinct by nature. I like functional code, data driven, and clean code. And above all–I hate overcomplicated OOP slop. Code with a bunch of if-statements instead of O(1) lookup from existing data structures is unacceptable, like wise long if/else:ing instead of e.g. checking membership in a list. Still, be pragmatic and don't be dogmatic about it. If OOP is the right tool for the job, use it, but don't use it just for the sake of using it.

## Development Commands

- Run the bot: `uv run dumpbot`
- Run tests: `uv run python test_bot.py`
- Deploy: `./deploy.sh`

## Integration Notes

This bot feeds into the nsnodes digest pipeline (../digest/) as data to drive claude's narrative.