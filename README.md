# Mergifyio/ci-benchmark-tooling

This README contains pricing information for all the CI providers compared by the benchmarks.

## CircleCI

Payment is "credit" based.  
Credit usage per minute per machine type: <https://circleci.com/product/features/resource-classes/>  
Pricing comparison per plan: <https://circleci.com/pricing/#comparison-table>  
Additional infos on credit usage: <https://circleci.com/docs/credits/>  

## GitHub

Payment is minute based.  
The base minute price is $0.008 USD per GB of storage per day and per-minute usage.  
⚠️ GitHub rounds the minutes and partial minutes each job uses up to the nearest whole minute.  

### [Number of minutes and storage per GitHub plan]( <https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions#included-storage-and-minutes>):
If your account's usage surpasses these limits and you have set a spending limit above $0 USD, you will pay based on the base minute price specified above.
| Product | Storage | Minutes included (per month) | [Plan price (USD)](<https://github.com/pricing>) |
|:--------|:-------:|:-------------------:|:-------:|
| GitHub Free | 500 MB | 2,000 | $0 |
| GitHub Pro | 1 GB | 3,000 | $4/user/month |
| GitHub Free for organizations | 500 MB | 2,000 | $0 |
| GitHub Team | 2 GB | 3,000 | $4/user/month |
| GitHub Enterprise Cloud | 50 GB | 50,000 | $21/user/month |

### [Minute multipliers per OS](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions#minute-multipliers)
| Operating system | Minute multiplier |
|:----------------:|:-----------------:|
| Linux | 1 |
| Windows | 2 |
| macOS | 10 |

Example list of [per-minute rates](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions#minute-multipliers) for different operating system and different number of cores (minute multipliers already applied):
| Operating system | Cores | Per-minute rate (USD) | [Availability](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners#supported-runners-and-hardware-resources) |
|:----------------:|:-----:|:---------------------:|:------------:|
| Linux | 2 | $0.008 | Github Free |
| Linux | 4 | $0.016 | GitHub Team |
| Linux | 8 | $0.032 | GitHub Team |
| Linux | 16 | $0.064 | GitHub Team |
| Linux | 32 | $0.128 | GitHub Team |
| Linux | 64 | $0.256 | GitHub Team |
| Windows | 2 | $0.016 | GitHub Free |
| Windows | 8 | $0.064 | GitHub Team |
| Windows | 16 | $0.128 | GitHub Team |
| Windows | 32 | $0.256 | GitHub Team |
| Windows | 64 | $0.512 | GitHub Team |
| macOS | 3 | $0.08 | GitHub Free |
| macOS | 12 | $0.32 | GitHub Free |
