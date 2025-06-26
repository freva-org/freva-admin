"""Script that prepares a new release of a version."""

import abc
import argparse
import json
import logging
import os
import re
import tempfile
from datetime import date
from functools import cached_property
from itertools import product
from pathlib import Path
from typing import Dict

import git
import requests
import tomli
from packaging.version import InvalidVersion, Version

# Set up logging
logging.basicConfig(
    format="%(name)s - %(levelname)s - %(message)s",
    datefmt="[%X]",
    level=logging.INFO,
)


logger = logging.getLogger("create-release")


class Release:
    """Abstract class for defining release jobs."""

    version_pattern: str = (
        r"__version__\s*=\s*['\"](\d+(\.\d+)*(-[a-zA-Z0-9]+)?)[\"']"
    )

    @abc.abstractmethod
    def __init__(
        self,
        package_name: str,
        repo_dir: str,
        branch: str = "main",
        search_path: str = ".",
        **kwargs: str,
    ) -> None:
        """Abstract init method."""

    @abc.abstractmethod
    def main(self) -> None:
        """Abstract main method."""


def cli(temp_dir: str) -> "Release":
    """Command line interface."""

    parser = argparse.ArgumentParser(
        description="Prepare the release of a package."
    )
    subparser = parser.add_subparsers(help="Available commands:")
    tag_parser = subparser.add_parser("tag", help="Create a new tag")
    deploy_parser = subparser.add_parser(
        "deploy", help="Update the version in the deployment repository"
    )
    for _parser in tag_parser, deploy_parser:
        _parser.add_argument("name", help="The name of the software/package.")
        _parser.add_argument(
            "-p", "--path", help="Set the search path.", type=str, default="."
        )
        _parser.add_argument(
            "-v",
            "--verbose",
            help="Enable debug mode.",
            action="store_true",
        )
        _parser.add_argument(
            "-b",
            "--branch",
            help="Set the working branch",
            type=str,
            default="main",
        )
    deploy_parser.add_argument(
        "-s",
        "--services",
        help="Additional services and their versions.",
        type=str,
        nargs=2,
        action="append",
    )
    tag_parser.set_defaults(apply_func=Tag)
    deploy_parser.set_defaults(apply_func=Bump)
    args = parser.parse_args()
    kwargs = {}
    if hasattr(args, "services"):
        kwargs = {s: v for (s, v) in args.services or ()}
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    return args.apply_func(args.name, temp_dir, args.branch, args.path, **kwargs)


class Exit(Exception):
    """Custom error class for representing specific errors.

    Attributes:
        message (str): A human-readable message describing the error.
        code (int): An error code associated with the error.
    """

    def __init__(self, message: str, code: int = 1) -> None:
        """Initialize the CustomError instance with the given message and error code.

        Args:
            message (str): A human-readable message describing the error.
            code (int): An error code associated with the error.
        """
        super().__init__(message)
        self.message = message
        logger.exception(message)
        raise SystemExit(code)


class Bump(Release):
    """Bump the version."""

    url = "https://api.github.com/repos/freva-org/freva-admin/pulls"

    def __init__(
        self,
        package_name: str,
        repo_dir: str,
        branch: str = "main",
        search_path: str = ".",
        **kwargs: str,
    ) -> None:
        self.extra_packages = kwargs
        self.version = os.environ.get("REPO_VERSION", "").strip("v")
        token = os.environ.get("GITHUB_TOKEN", "")
        self.branch = branch
        self.package_name = package_name
        self.repo_dir = Path(repo_dir)
        self.search_path = search_path
        self.repo_url = f"https://{token}@github.com/freva-org/freva-admin.git"
        logger.debug(
            "Cloning repository from %s with branch %s to %s",
            self.repo_url,
            self.repo_dir,
            branch,
        )
        self.repo = git.Repo.clone_from(
            self.repo_url, self.repo_dir, branch=branch
        )

    @property
    def repo_name(self) -> str:
        repo = git.Repo(search_parent_directories=True)
        name = repo.remotes.origin.url.split("/")[-1].replace(".git", "")
        return self.lookup.get(name, name)

    @property
    def lookup(self) -> Dict[str, str]:
        return {
            "freva-web": "web",
            "databrowserAPI": "databrowser",
            "freva": "core",
        }

    def update_whatsnew(self) -> None:
        """Update the whats new section."""
        file = Path(self.repo_dir / "docs" / "whatsnew.rst")
        service = {v: k for k, v in self.lookup.items()}.get(
            self.package_name, self.package_name
        )
        new_content = (
            f":titlesonly:\n\nv{self.deploy_version}\n"
            f"{'~'*len(self.deploy_version.public)}\n"
            f"* Bumped version of {service} to "
            f"{self.version}\n\n"
        )
        file.write_text(file.read_text().replace(":titlesonly:", new_content))

    @cached_property
    def deploy_version(self) -> str:
        """Get the deployment version."""
        version_tuple = self.old_deploy_version.release
        major = int(date.today().strftime("%y%m"))
        if major > version_tuple[0]:
            new_version = Version(f"{major}.0.0")
        else:
            new_version = Version(f"{version_tuple[0]}.{version_tuple[1]+1}.0")
        return new_version

    @cached_property
    def old_deploy_version(self) -> str:
        """Get the current deployment version."""
        file = Path(self.repo_dir / "src" / "freva_deployment" / "__init__.py")
        match = re.search(self.version_pattern, file.read_text())
        if not match:
            raise ValueError("Could not find frev-deployment version")
        return Version(match.group(1))

    def main(self) -> None:
        """Do the main work."""
        self.update_whatsnew()
        file = Path(self.repo_dir / "src" / "freva_deployment" / "__init__.py")
        service_file = file.parent / "versions.json"
        logger.debug("Looking for version")
        logger.debug("New version is %s", self.deploy_version.public)
        file_content = file.read_text().replace(
            self.old_deploy_version.public, self.deploy_version.public
        )
        logger.debug("Updating service versions.")
        file.write_text(file_content)
        versions = json.loads(service_file.read_text())
        versions[self.package_name] = self.version
        versions["vault"] = self.deploy_version.public
        for service, vers in self.extra_packages.items():
            versions[service] = vers
        service_file.write_text(json.dumps(versions, indent=3))
        branch = f"bump-{self.package_name}-{self.version}"
        logger.debug("Creating new branch %s", branch)
        self.repo.create_head(branch)
        self.repo.git.checkout(branch)
        self.repo.index.add("*")
        commit_message = f"Bump {self.package_name} version to {self.version}"
        self.repo.index.commit(commit_message)
        origin = self.repo.remote(name="origin")
        logger.debug("Submitting PR")
        origin.set_url(self.repo_url)
        origin.push(branch)
        self.submit_pr(branch)

    def submit_pr(self, branch: str) -> str:
        """Submit a PR on the deployment repo."""

        # Data for the pull request
        data = {
            "title": f"Bump {self.package_name} version to {self.version}",
            "head": branch,  # Source branch
            "base": self.branch,  # Target branch
            "body": (
                f"This PR auto bumps the version of {self.package_name}"
                f" to {self.version}. After the PR is merged you can create"
                " a new release of the deployment software by creating a"
                f" tag with the name v{self.version} or, better by following "
                "the release procedure:\n\n```console\ntox -e release\n```\n"
            ),
        }
        headers = {
            "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        logger.info("Creating PR")
        response = requests.post(self.url, json=data, headers=headers)
        # Check if pull request was successfully created
        if response.status_code == 201:
            logger.debug("Pull request created successfully!")
        else:
            raise Exit("Failed to create pull request:%s", response.text)


class Tag(Release):
    """Tag class."""

    def __init__(
        self,
        package_name: str,
        repo_dir: str,
        branch: str = "main",
        search_path: str = ".",
        version: str = "",
        **kwargs: str,
    ) -> None:
        self.branch = branch
        self.package_name = package_name
        self.repo_dir = Path(repo_dir)
        self.search_path = search_path
        logger.info(
            "Searching for packages/config with the name: %s", package_name
        )
        logger.debug("Reading current git config")
        self.git_config = (
            Path(git.Repo(search_parent_directories=True).git_dir) / "config"
        ).read_text()
        if os.environ.get("GIT_USER"):
            append = """[user]
    name = {user}
    email = {user}@users.noreply.github.com
    """.format(
                user=os.environ.get("GIT_USER")
            )
            self.git_config += "\n"
            self.git_config += append

    def tag_version(self) -> None:
        """Tag the latest git version."""

    @cached_property
    def repo_url(self) -> str:
        """Get the current git repo url."""
        repo = git.Repo(search_parent_directories=True)
        url = repo.remotes.origin.url
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            url = url.replace("https://", f"https://{token}@")
        return url

    @cached_property
    def git_tag(self) -> Version:
        """Get the latest git tag."""
        logger.debug("Searching for the latest tag")
        repo = git.Repo(self.repo_dir)
        try:
            # Get the latest tag on the main branch
            return Version(
                repo.git.describe("--tags", "--abbrev=0", self.branch).lstrip("v")
            )
        except git.exc.GitCommandError:
            logger.debug("No tag found")
        except InvalidVersion:
            logger.debug("Tag found, but could not parse version")
        return Version("0.0.0")

    @property
    def version(self) -> Version:
        """Get the version of the current software."""
        logger.debug("Searching for software version.")
        pck_dirs = Path(self.search_path) / Path("src") / self.package_name, Path(
            self.search_path
        ) / Path("src") / self.package_name.replace("-", "_")
        files = [
            self.repo_dir / f[1] / f[0]
            for f in product(("_version.py", "__init__.py"), pck_dirs)
        ]
        files += [
            self.repo_dir / self.search_path / Path("package.json"),
            self.repo_dir / self.search_path / "pyproject.toml",
        ]
        for file in files:
            if file.is_file():
                if file.suffix == ".py":
                    match = re.search(self.version_pattern, file.read_text())
                    if match:
                        return Version(match.group(1))
                elif file.suffix == ".json":
                    content = json.loads(file.read_text())
                    if "version" in content:
                        return Version(content["version"])
                elif file.suffix == ".toml":
                    content = tomli.loads(file.read_text())
                    if "project" in content and "version" in content["project"]:
                        return Version(content["project"]["version"])
        raise ValueError("Could not find version")

    def _clone_repo_from_branch(self, branch: str = "main") -> None:
        logger.debug(
            "Cloning repository from %s with branch %s to %s",
            self.repo_url,
            self.repo_dir,
            branch,
        )
        git.Repo.clone_from(self.repo_url, self.repo_dir, branch=branch)
        (self.repo_dir / ".git" / "config").write_text(self.git_config)

    def _check_change_log_file(self) -> None:
        """Check if the current version was added to the change log file."""
        logger.debug("Checking for change log file.")
        version = self.version
        dev_rc_keywords = ["dev", "rc", "alpha", "beta"]
        if any(keyword in str(version) for keyword in dev_rc_keywords):
            return
        if not self._change_log_file.is_file():
            raise Exit(
                "Could not find change log file. "
                f"Create one first and push it to the {self.branch} branch."
            )
        if f"v{version}" not in self._change_log_file.read_text("utf-8"):
            raise Exit(
                "You need to add the version v{} to the {} change log file "
                "and push the update to the {} branch".format(
                    version,
                    self._change_log_file.relative_to(self.repo_dir),
                    self.branch,
                )
            )

    @cached_property
    def _change_log_file(self) -> Path:
        """Find the change log file."""
        for prefix, suffix in product(
            ("changelog", "whats-new", "whatsnew"), (".rst", ".md")
        ):
            for search_pattern in (prefix, prefix.upper()):
                glob_pattern = f"{search_pattern}{suffix}"
                logger.debug("Searching for %s", glob_pattern)
                for file in self.repo_dir.rglob(glob_pattern):
                    return file
        return Path(tempfile.mktemp())

    def main(self) -> None:
        """Tag a new git version."""
        self._clone_repo_from_branch(self.branch)
        cloned_repo = git.Repo(self.repo_dir)
        remote = cloned_repo.remote(name="origin")
        url = cloned_repo.remotes.origin.url
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            url = url.replace("https://", f"https://{token}@")
            logger.info("Setting remote url to %s", url)
        remote.set_url(url)
        if self.version <= self.git_tag:
            raise Exit(
                "Tag version: {} is the same as current version {}"
                ", you need to bump the verion number first and "
                "push the changes to the {} branch".format(
                    self.version,
                    self.git_tag,
                    self.branch,
                )
            )
        self._check_change_log_file()
        logger.info("Creating tag for version v%s", self.version)
        head = cloned_repo.head.reference
        message = f"Create a release for v{self.version}"
        try:
            cloned_repo.create_tag(f"v{self.version}", ref=head, message=message)
            cloned_repo.git.push("--tags")
        except git.GitCommandError as error:
            raise Exit("Could not create tag: {}".format(error))
        logger.info("Tags created.")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temporary_dir:
        try:
            release = cli(temporary_dir)
            release.main()
        except Exception as error:
            if logger.getEffectiveLevel() == logging.DEBUG:
                raise
            raise Exit("An error occurred: {}".format(error)) from error
