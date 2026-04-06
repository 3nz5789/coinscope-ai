# Contributing to CoinScopeAI

First off, thank you for considering contributing to CoinScopeAI! It's people like you that make CoinScopeAI such a great tool.

## 1. Where do I go from here?

If you've noticed a bug or have a feature request, make sure to check our [Issues](https://github.com/3nz5789/coinscope-ai/issues) to see if someone else has already created a ticket. If not, go ahead and make one!

## 2. Fork & create a branch

If this is something you think you can fix, then fork CoinScopeAI and create a branch with a descriptive name.

A good branch name would be (where issue #325 is the ticket you're working on):

```sh
git checkout -b 325-add-new-indicator
```

## 3. Get the test suite running

Make sure you have the required dependencies installed and run the test suite to ensure everything is working before you start making changes.

```sh
# Example for backend
cd services/trading-engine
pip install -r requirements.txt
pytest
```

## 4. Implement your fix or feature

At this point, you're ready to make your changes. Feel free to ask for help; everyone is a beginner at first.

## 5. Make a Pull Request

At this point, you should switch back to your master branch and make sure it's up to date with CoinScopeAI's master branch:

```sh
git remote add upstream git@github.com:3nz5789/coinscope-ai.git
git checkout main
git pull upstream main
```

Then update your feature branch from your local copy of main, and push it!

```sh
git checkout 325-add-new-indicator
git rebase main
git push --set-upstream origin 325-add-new-indicator
```

Finally, go to GitHub and make a Pull Request.

## 6. Keeping your Pull Request updated

If a maintainer asks you to "rebase" your PR, they're saying that a lot of code has changed, and that you need to update your branch so it's easier to merge.

## Code of Conduct

Please note that this project is released with a Contributor Code of Conduct. By participating in this project you agree to abide by its terms.
