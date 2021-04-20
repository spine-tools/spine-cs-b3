#=
run_spineopt_test:
- Julia version: 
- Author: jhjiang
- Date: 2020-10-01
=#
# syntax to run this script

using SpineOpt
using IJulia

if isdefined(Main, :IJulia) && Main.IJulia.inited
    IJulia.set_max_stdio(1 << 25)
end

input_db_url = ARGS[1]
output_db_url = ARGS[2]
@time begin
    m = run_spineopt(input_db_url, output_db_url; cleanup=true, optimize=true)
end

# Show active variables and constraints
println("*** Active constraints: ***")
for key in keys(m.ext[:constraints])
    !isempty(m.ext[:constraints][key]) && println(key)
end
println("*** Active variables: ***")
for key in keys(m.ext[:variables])
    !isempty(m.ext[:variables][key]) && println(key)
end
