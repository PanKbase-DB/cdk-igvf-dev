# cdk-igvf-dev
This repo is for defining and deploying infrastructure in the `igvf-dev` account that is shared or outlives a particular application's lifecycle (VPCs, security groups, etc).

## Type checking with Mypy
Type annotations can be statically checked with `mypy`:
```bash
$ pip install -r requirements-dev.txt
$ mypy --strict .
```