# GitHub submission guide

The project is prepared as a local Git repository. The original contest tutorial says the final GitHub repository must be visible to judges; a local folder or private inaccessible repository will not meet that access expectation. No GitHub repository was created or published automatically.

## Publish the prepared repository

1. Sign in to your team's GitHub account and create an empty repository named **gridweave**. Select public visibility when you are ready for judge access. Do not initialize a second README or license: both are already here.
2. Open a terminal in this project folder. Set the team's identity for future commits, using the team's actual details:

```bash
git config user.name "YOUR TEAM NAME"
git config user.email "YOUR ACTUAL GIT EMAIL"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/gridweave.git
git push -u origin main
```

The prepared initial commit uses the project identity “GridWeave Contributors”; it does not impersonate a team member. The identity commands above affect this repository only. Do not put access tokens in a remote URL or commit credentials. GitHub's normal sign-in/credential flow handles authentication.

3. Open the repository while signed out or in a private browser window. Confirm that the README, source, results, and documentation can be viewed. Let GitHub Actions finish and inspect its actual status rather than claiming CI success in advance.
4. Submit the GitHub repository URL through the contest's official submission channel. That final contest submission is not performed by this project.

## Final review

- Run `python -m unittest discover -s tests -v`.
- Run `python -m gridweave validate results/demo.json`.
- Follow the README's start commands from a clean checkout.
- Verify that any presentation numbers match committed results, with synthetic data disclosed.
- Replace no evidence with guessed results; include limitations and explain the model's optimality scope.
- Confirm your team's name, author information, and contest requirements outside these two supplied documents.

## Sharing the local Git bundle

The delivered `gridweave.bundle` contains the complete committed Git history. It does not contain the virtual environment. To make another checkout:

```bash
git clone /path/to/gridweave.bundle gridweave
cd gridweave
```

Then follow the README to install dependencies and run the project. The Git bundle is a portable repository, not a published GitHub URL.
