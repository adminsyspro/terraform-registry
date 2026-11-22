# ProxCenter Terraform registry

The static [provider registry](https://developer.hashicorp.com/terraform/internals/provider-registry-protocol) served at **https://registry.proxcenter.io**.

```terraform
terraform {
  required_providers {
    proxcenter = {
      source  = "registry.proxcenter.io/adminsyspro/proxcenter"
      version = "~> 0.2"
    }
  }
}
```

`terraform init` then installs the provider and checks its GPG signature.

## How it works

- `public/` holds the registry documents: the service discovery file, the version list, and one download document per version and platform. Cloudflare Pages serves it as is.
- The provider binaries are not stored here. Each download document points at the signed assets of the GitHub release of [terraform-provider-proxcenter](https://github.com/adminsyspro/terraform-provider-proxcenter).
- `scripts/generate.py` rebuilds `public/` from those releases. The *Update registry* workflow runs it every 30 minutes and pushes when a release was added.

Signing key: `E6F5F38BE03A888F` ([scripts/proxcenter-provider-signing-key.asc](scripts/proxcenter-provider-signing-key.asc)).
