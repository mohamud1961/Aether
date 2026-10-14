# Config layers

Each service directory holds:

- `base.yaml`: defaults shared by every environment.
- `overrides/<environment>.yaml`: keys set for one environment. A key set here wins over `base.yaml`.
  Keys the overlay does not set come from `base.yaml`.

The deploy manifest's `profile_file` names the profile in use. The profile gives the `environment`
and the `active_service`. The overlay for that service and environment is
`services/<active_service>/overrides/<environment>.yaml`.

`base.yaml` changes affect every environment. Environment-specific changes belong in the overlay.
