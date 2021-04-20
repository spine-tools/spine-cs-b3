using Pkg

# Set Julia environment path
juliaenv = ".julia"

# Activate environment
Pkg.activate(juliaenv)

# Set Julia development dir
ENV["JULIA_PKG_DEVDIR"] = abspath(juliaenv)

# Add Spine package registry
pkg"registry add https://github.com/Spine-project/SpineJuliaRegistry.git"

# Add packages from Project.toml
Pkg.instantiate()

### Other examples #############################################################
## Download the source for development (will go in `JULIA_PKG_DEVDIR`)
# Pkg.develop(PackageSpec(url="https://github.com/Spine-project/SpineOpt.jl"))
# 
## Specify commit hashes
# Pkg.add(PackageSpec(url="https://github.com/Spine-project/SpineInterface.jl.git", 
#                     rev="ebe87b8c3ccbf046d44cf30b66a9ad8830b0e477"))
# Pkg.add(PackageSpec(url="https://github.com/Spine-project/SpineOpt.jl", 
#                     rev="71ff747f64ae9d318a18f223c67c6b409928cf34"))
################################################################################

