// Find instructions that use a given displacement (e.g. [reg+0x5c4]) and decompile their functions.
// args: <outfile> <hexdisp> [<hexdisp> ...]
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.scalar.Scalar;
import java.io.PrintWriter;
import java.util.LinkedHashSet;

public class FindOffsetUses extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        LinkedHashSet<Long> disps = new LinkedHashSet<>();
        for (int i = 1; i < args.length; i++) disps.add(Long.parseLong(args[i], 16));
        LinkedHashSet<Function> funcs = new LinkedHashSet<>();
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            InstructionIterator it = currentProgram.getListing().getInstructions(true);
            while (it.hasNext()) {
                Instruction ins = it.next();
                for (int op = 0; op < ins.getNumOperands(); op++) {
                    for (Object o : ins.getOpObjects(op)) {
                        if (o instanceof Scalar && disps.contains(((Scalar) o).getUnsignedValue())
                                && ins.getDefaultOperandRepresentation(op).contains("[")) {
                            Function f = getFunctionContaining(ins.getAddress());
                            out.println("// " + ins.getAddress() + " " + ins + " in " + (f == null ? "?" : f.getName()));
                            if (f != null) funcs.add(f);
                        }
                    }
                }
            }
            DecompInterface di = new DecompInterface();
            di.openProgram(currentProgram);
            for (Function f : funcs) {
                DecompileResults r = di.decompileFunction(f, 120, monitor);
                out.println("// ===== " + f.getName() + " @ " + f.getEntryPoint());
                out.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// failed");
            }
            di.dispose();
        }
    }
}
