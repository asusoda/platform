"""The write rule of the github.* tools. No Flask here.

A write runs only on one of the org's linked repos. With no linked repos, every write is refused. A file write names a branch
that is not the repo's default branch. A merge runs only when the pull request is open and every check
on its head commit passed. Reads are not checked here.
"""

from core.integrations import github
from core.integrations.registry import IntegrationError
from core.tools import ToolError

# Tools that change files on a branch
FILE_WRITES = {"create_or_update_file", "push_files", "delete_file"}
MERGES = {"merge_pull_request"}


def check(org, headers: dict[str, str], tool_name: str, target: str | None, arguments: dict) -> None:
    """Raise ToolError when the write breaks the rule. headers sign in with the org's GitHub token."""
    linked = [repo.lower() for repo in github.linked_repos(org)]
    if not linked:
        raise ToolError(
            "The org lists no linked repos, so agents may not write to GitHub. "
            "Officers list them on the Activity page, CI tab",
            403,
        )
    if target not in linked:
        raise ToolError(
            f"{target or 'This write'} is not a linked repo. Linked repos: {', '.join(linked)}. "
            "Officers change the list on the Activity page, CI tab",
            403,
        )
    if tool_name not in FILE_WRITES | MERGES:
        return
    if target is None:
        raise ToolError("Name the repo with owner and repo", 400)
    token = headers.get("Authorization", "").removeprefix("Bearer ")
    try:
        if tool_name in FILE_WRITES:
            _check_branch(token, target, arguments.get("branch"))
        else:
            _check_merge(token, target, arguments.get("pullNumber"))
    except IntegrationError as e:
        raise ToolError(f"github: {e}", 502) from e


def _check_branch(token: str, repo: str, branch: object) -> None:
    if not isinstance(branch, str) or not branch.strip():
        raise ToolError("Name a branch. Writes go to a branch and a pull request, never the default branch", 400)
    if branch.strip() == github.default_branch(token, repo):
        raise ToolError(f"{branch} is the default branch of {repo}. Push to a new branch and open a pull request", 403)


def _check_merge(token: str, repo: str, number: object) -> None:
    if isinstance(number, bool) or not isinstance(number, int | str) or not str(number).isdigit():
        raise ToolError("Name the pull request with pullNumber", 400)
    reason = github.unmet_checks(token, repo, int(number))
    if reason:
        raise ToolError(f"Not merged: {reason}. Merge when every check passed", 409)
