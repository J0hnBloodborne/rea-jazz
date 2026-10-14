// Decompile functions that reference each address arg ("ref:<hex>") or contain it ("<hex>").
// args: <outfile> <spec> [<spec> ...]
// Run: analyzeHeadless <projdir> ak992 -process DeviceDriver.exe -noanalysis -readOnly
//        -scriptPath tools/ghidra_scripts -postScript DecompileRefs.java out.c ref:54c7a1 405500
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;

public class DecompileRefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        LinkedHashSet<Function> seen = new LinkedHashSet<>();
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i = 1; i < args.length; i++) {
                String spec = args[i];
                List<Function> fs = new ArrayList<>();
                if (spec.startsWith("ref:")) {
                    Address a = toAddr(Long.parseLong(spec.substring(4), 16));
                    for (Reference r : getReferencesTo(a)) {
                        Function f = getFunctionContaining(r.getFromAddress());
                        out.println("// ref to " + a + " from " + r.getFromAddress() + " in " + (f == null ? "?" : f.getName()));
                        if (f != null) fs.add(f);
                    }
                } else {
                    Function f = getFunctionContaining(toAddr(Long.parseLong(spec, 16)));
                    if (f != null) fs.add(f);
                }
                for (Function f : fs) {
                    if (!seen.add(f)) continue;
                    DecompileResults r = di.decompileFunction(f, 120, monitor);
                    out.println("// ===== " + f.getName() + " @ " + f.getEntryPoint() + " (spec " + spec + ")");
                    out.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// decompile failed: " + r.getErrorMessage());
                }
            }
        }
        di.dispose();
    }
}
