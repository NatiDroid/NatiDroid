package javaLink;


import com.google.common.collect.Lists;
import soot.*;
import soot.jimple.StringConstant;
import soot.jimple.internal.JAssignStmt;
import soot.jimple.internal.JInvokeStmt;
import soot.jimple.spark.SparkTransformer;
import soot.jimple.toolkits.callgraph.*;
import soot.options.Options;
import util.config;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;


public class JavaLink extends SceneTransformer {

    public static boolean RUN_ON_MAC = true;
    public static ArrayList<String> uniqueMethodList = new ArrayList();

    static LinkedList<String> excludeList;


    static String mainClassStrLast = "ICameraService$Stub$Proxy";
    static String mainClassStr = "android.hardware." + mainClassStrLast;
    static ArrayList<String> starts_call = new ArrayList<String>();
    static SootClass mainClass = null;

    public static void run(String mainClassStrLast, String mainClassStr, int mode, ArrayList<String> starts_call) {
        ArrayList<String> supportClassList = new ArrayList<String>();
        run(mainClassStrLast, mainClassStr, mode, starts_call, supportClassList);
    }

    public static void run(String mainClassStrLast, String mainClassStr, int mode, ArrayList<String> starts_call, ArrayList<String> supportClassList){
        String mode1 = "wjtp.parent_call";
        String mode2 = "wjtp.permission_finder";
        String transform_str = mode1;
        if (mode ==1) {
            transform_str = mode1;
        }else if(mode ==2) {
            transform_str = mode2;
        }
        JavaLink.mainClassStrLast = mainClassStrLast;
        JavaLink.mainClassStr = mainClassStr;
        JavaLink.starts_call = starts_call;



        String javapath = "";


        String jreDir = config.loadJreDir(RUN_ON_MAC);
        String jceDir = config.loadJceDir(RUN_ON_MAC);

        String path = config.loadJarPath();
        System.out.println(path);

        Scene.v().setSootClassPath(path);


        //add an intra-procedural analysis phase to Soot
        JavaLink analysis = new JavaLink();
        PackManager.v().getPack("wjtp").add(new Transform(transform_str, analysis));


        excludeJDKLibrary();


        Options.v().set_whole_program(true);
        Options.v().set_app(true);
        Options.v().set_validate(true);



        SootClass c = Scene.v().forceResolve(mainClassStr, SootClass.BODIES);
        for(String classTem : supportClassList){
            Scene.v().forceResolve(classTem, SootClass.BODIES);
        }

        c.setApplicationClass();

        Scene.v().loadNecessaryClasses();


        //Set all entrypoint and find mainclass
        List<SootMethod> entryPoints = new ArrayList<SootMethod>();
        for(SootClass sc : Scene.v().getApplicationClasses()) {
            if(!sc.getName().contains("jdk.")){

                //Output all loaded class names
                System.err.println(sc);

                if(sc.getName().equals(mainClassStr)){
                    mainClass = sc;
                }


                for (SootMethod m : sc.getMethods()) {
                    entryPoints.add(m);
                }
            }
        }

        if(mainClass==null){
            System.err.println("The specified mainClass was not found");
            System.exit(0);
        }

        Scene.v().setEntryPoints(entryPoints);


        //enable call graph
        enableCHACallGraph();

        PackManager.v().runPacks();
        System.out.println("=============");
        System.out.println("=============");
        System.out.println("=============");
        for(String tem: uniqueMethodList){

            Pattern p = Pattern.compile("\\$[0-9]+");
            Matcher m = p.matcher(tem);
            if(!m.find()){
                System.out.println(tem);
            }

        }
    }

    private static void excludeJDKLibrary()
    {
        Options.v().set_exclude(excludeList());
        Options.v().set_no_bodies_for_excluded(true);
        Options.v().set_allow_phantom_refs(true);
    }

    private static void enableSparkCallGraph() {
        /*
         -verbose. (Set SPARK to print a variety of information [prompt information] during the analysis process)
         -propagator SPARK. (Contains two propagation algorithms, native iterative algorithm, and worklist-based algorithm)
         -simple-edges-bidirectional. (If set to true, all edges are bidirectional)
         -on-fly-cg. (By setting this option, a more accurate points-to analysis can be performed to obtain an accurate call graph)
         -set-impl. (Describe the realization of points-to set. Possible values are hash, bit, hybrid, array, double)
         -double-set-old and double-set-new.
         */
        //Enable Spark
        HashMap<String,String> opt = new HashMap<String,String>();
        opt.put("propagator","worklist");
        opt.put("simple-edges-bidirectional","false");
        opt.put("on-fly-cg","true");
        opt.put("set-impl","double");
        opt.put("double-set-old","hybrid");
        opt.put("double-set-new","hybrid");
        opt.put("pre_jimplify", "true");
        SparkTransformer.v().transform("",opt);
        PhaseOptions.v().setPhaseOption("cg.spark", "enabled:true");
    }

    private static void enableCHACallGraph() {
        CHATransformer.v().transform();
    }

    private static LinkedList<String> excludeList()
    {
        if(excludeList==null)
        {
            excludeList = new LinkedList<String> ();

            excludeList.add("java.");
            excludeList.add("javax.");
            excludeList.add("sun.");
            excludeList.add("sunw.");
            excludeList.add("com.sun.");
            excludeList.add("com.ibm.");
            excludeList.add("com.apple.");
            excludeList.add("apple.awt.");

            excludeList.add("android.os.Message");
            excludeList.add("android.os.Handler");

        }
        return excludeList;
    }

    public List<SootClass> getSUbclasses(SootClass c){
        List<SootClass> subclasses= new ArrayList<SootClass>();
        for (SootClass sc : Scene.v().getApplicationClasses()) {
            if(sc.hasSuperclass()){
                SootClass superClass = sc.getSuperclass();
                if(superClass.getName().equals(c.getName())){
                    subclasses.add(sc);
                }
            }
        }
        return subclasses;
    }


    public List<SootClass> getInnerClass(SootClass c){
        List<SootClass> innerClass= new ArrayList<SootClass>();
        for (SootClass sc : Scene.v().getApplicationClasses()) {
            if(sc.getName().contains(c.getName())){
                innerClass.add(sc);
            }
        }
        return innerClass;
    }

    public SootClass getInnerClass(SootClass c, String className){
        for (SootClass sc : Scene.v().getApplicationClasses()) {
            if(sc.getName().contains("$Proxy")){
                int u=0;
                boolean aaaaaaa = sc.getName().contains(c.getName()+"$"+className);
            }
            if(sc.getName().contains(c.getName()+"$"+className)){
                return sc;
            }
        }
        return null;
    }

    public SootClass getClass(String className){
        for (SootClass sc : Scene.v().getApplicationClasses()) {
            if(sc.getName().contains(className)){
                return sc;
            }
        }
        return null;
    }

    protected void pre_visit(SootMethod m, SootMethod p, CallGraph callGraph, CallGraph bigCallGraph, List<String> permissionStrs, List<String> visitedMethodSig){

        if(!visitedMethodSig.contains(m.getSignature())) {
            if(!m.getSignature().contains("$Stub: boolean onTransact(")){
                visitedMethodSig.add(m.getSignature());
            }
        }else{
            return;
        }

        //AIDL
        if(m.getSignature().contains("$Stub: boolean onTransact(")){
            //stub -> interface, interface -> Proxy
            SootClass classProxy = getInnerClass(m.getDeclaringClass(),"Proxy");
            SootMethod mthodInterface = classProxy.getMethod(p.getName(),p.getParameterTypes());
            System.out.println("===FROM=====" + m.toString() + "========");
            System.out.println("===TO=====" + mthodInterface.toString() + "========");
            m = mthodInterface;

        }

        // CFG reverse retrospective termination API The first two involve handler processing
        // onReceive onChange are listeners that cannot be traced upwards

        if(m.getDeclaringClass().getName().contains("android.os.Handler") || m.getSignature().contains("handleMessage(android.os.Message)")){
            return;

        }else if(m.getDeclaringClass().getName().contains("android.content.Intent")){
            return;

        }else if(m.getDeclaringClass().getName().contains("java.lang.Thread")){
            return;

        }else if (m.getSignature().contains("void on")) {
            return;

        }
        else if (m.getSignature().contains("void run(")) {

        }
        else if (m.getSignature().contains("createFromParcel(")) {
        // <android.bluetooth.BluetoothDevice$2: java.lang.Object createFromParcel(android.os.Parcel)>
            return;
        }else if (m.getSignature().contains("android.os.Binder")) {
        // <android.bluetooth.BluetoothDevice$2: java.lang.Object createFromParcel(android.os.Parcel)>
            return;
        }





        if(m.getDeclaringClass().isAbstract() || m.getDeclaringClass().isInterface())
        {
            System.out.println(PrintColor.ANSI_RED + m + "isAbstract "+ m.getDeclaringClass().isAbstract() + ";isInterface "+ m.getDeclaringClass().isInterface() + PrintColor.ANSI_RESET);
            return;
        }

        //Find all the function input methods that contain the object theoretically require permissions
        if (m.getSignature().contains("void <init>")) {

            //Traverse to find the parameter type of the init class
            String findClass = m.getDeclaringClass().getName();
            for(SootClass sc : Scene.v().getApplicationClasses()) {
                if (!sc.getName().contains("jdk.")&& !sc.isAbstract() && !sc.isInterface()) {
                    for(SootMethod temm : sc.getMethods()) {
                        List<Type> types= temm.getParameterTypes();
                        for(Type typeTem : types) {
                            if(typeTem.toString().equals(findClass)){
                                pre_visit(temm, m, callGraph, bigCallGraph, permissionStrs, visitedMethodSig);
                                break;
                            }
                        }
                    }
                }
            }
        }


        //Perform normal CFG analysis
        //Nothing wrong, keep going.
        Iterator<Edge> temEdgesIterator = callGraph.edgesInto(m);
        Iterator<MethodOrMethodContext> parents = new Sources(temEdgesIterator);
        if (m.getSignature().contains("void run(")){
            while (parents.hasNext()) {
                SootMethod parent = (SootMethod) parents.next();
                if(!m.getDeclaringClass().hasOuterClass()){
                    System.out.println("run( not inner run() " + parent);
                    return;
                }
                if(parent.getDeclaringClass().toString().equals(m.getDeclaringClass().getOuterClass().toString())){
                    System.out.println("run( parent FOUND " + parent);

                    pre_visit(parent, m, callGraph, bigCallGraph, permissionStrs, visitedMethodSig);
                    return;
                }

            }
            return;

        }


        if (parents == null) {
            return;
        }

        while (parents.hasNext()) {
            SootMethod parent = (SootMethod) parents.next();

            if(m.getSignature().contains("view")){
                int pppp = 0;
            }
            boolean found = false;
            for(String tem_method : uniqueMethodList)
            {
                if(tem_method.equals(parent.toString())){
                    found = true;
                    break;
                }
            }
            if(!found){
                uniqueMethodList.add(parent.toString());
            }

            System.out.println(PrintColor.ANSI_RESET + m + PrintColor.ANSI_GREEN + " <=== " + parent + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);

            if(!parent.getDeclaringClass().getName().contains("location") && !parent.getDeclaringClass().getName().contains("Location")){
                int a =0;
            }


            pre_visit(parent, m, callGraph, bigCallGraph, permissionStrs, visitedMethodSig);

        }



    }

    class PermissionMthod{
        public SootMethod parentMethod;
        public List<String> permissionStrs;

        PermissionMthod(SootMethod parentMethod, List<String> permissionStrs){
            this.parentMethod = parentMethod;
            this.permissionStrs = permissionStrs;
        }
    }

    //Find a method for permission detection and store the requested permission
    public List<String> methodHasCheckPermission(SootMethod m){
        List<String> permissionStrs = new ArrayList<String>();

        if(m.isNative()){
            return permissionStrs;
        }
        Body fun = m.getActiveBody();

        //Traverse the code block where the function is located
        for(Unit u: fun.getUnits()) {
            String unitStrTem = u.toString();
            if(unitStrTem.contains("checkPermission(")||unitStrTem.contains("checkCallingPermission(")||unitStrTem.contains("checkCallingOrSelfPermission(")
                    ||unitStrTem.contains("enforcePermission(")||unitStrTem.contains("enforceCallingPermission(")||unitStrTem.contains("enforceCallingOrSelfPermission(")){

                if(u instanceof JAssignStmt) {
                    Value v = ((JAssignStmt) u).getRightOpBox().getValue();
                    for (ValueBox vvv : v.getUseBoxes()) {
                        if (vvv.getValue() instanceof StringConstant) {
                            //check的permission
                            String permissionStr = ((StringConstant) vvv.getValue()).value;
                            permissionStrs.add(permissionStr);
                            break;
                        }
                    }
                }else if(u instanceof JInvokeStmt){
                    Value v = ((JInvokeStmt) u).getInvokeExprBox().getValue();
                    for (ValueBox vvv : v.getUseBoxes()) {
                        if (vvv.getValue() instanceof StringConstant) {
                            //check permission
                            String permissionStr = ((StringConstant) vvv.getValue()).value;
                            permissionStrs.add(permissionStr);
                            break;
                        }
                    }
                }else{
                    System.err.println("Unknown JxxStmt type");
                }
            }
        }
        return permissionStrs;
    }

    @Override
    protected void internalTransform(String phaseName,
                                     Map options) {
        CallGraph bigCallGraph = new CallGraph();
        CallGraph callGraph = Scene.v().getCallGraph();
        int sieze = callGraph.size();

        //search methods in mainclass which call checkPermission
        Map<String,PermissionMthod> serviceHasPermissionMethods = new HashMap<String,PermissionMthod>();

        List<SootMethod> mainClassMethodList = mainClass.getMethods();
        System.out.println(mainClassMethodList.size());

        if (mainClassMethodList.size() == 0) {
            System.out.println(mainClassStr + "DOES NOT EXIST");
        }
        for (SootMethod m : mainClassMethodList) {
            System.out.println(m);
        }

        // find permission
        if(phaseName.equals("wjtp.permission_finder")) {
            for (SootMethod m : mainClassMethodList) {

                List<String> permissionStrs = methodHasCheckPermission(m);
                if (permissionStrs.size() != 0) {
                    System.out.println(m + "  " + permissionStrs);
                    PermissionMthod permissionMthod = new PermissionMthod(m, permissionStrs);
                    serviceHasPermissionMethods.put(m.getSignature(), permissionMthod);
                }

            }


            for(PermissionMthod permissionMthod : serviceHasPermissionMethods.values()){
                SootMethod m = permissionMthod.parentMethod;
                List<String> visitedMethodSig = new ArrayList<String>();
                System.out.println("#########################");
                System.out.println("SEARCH FROM" + m + permissionMthod.permissionStrs);
                System.out.println("#########################");
                pre_visit(m, null, callGraph, bigCallGraph, permissionMthod.permissionStrs, visitedMethodSig);
            }
        }else if(phaseName.equals("wjtp.parent_call")) {

            // find parent
            for (SootMethod m : mainClassMethodList) {
                boolean contains = false;
                for (String fun : starts_call){
                    if (m.getSignature().contains(fun))
                        contains = true;
                }
                if (contains) {
                    List<String> visitedMethodSig = new ArrayList<String>();
                    System.out.println("#########################");
                    System.out.println("SEARCH FROM" + m);
                    System.out.println("#########################");
                    uniqueMethodList.add(m.toString());
                    List<String> permissionStrs = new ArrayList<String>();
                    pre_visit(m, null, callGraph, bigCallGraph, permissionStrs, visitedMethodSig);
                }
            }
        }else{
            System.out.println("Unsupported phaseName, Please check");
        }
        System.out.println("\n\n\n\n");

    }

    class PrintColor{
        public static final String ANSI_RESET = "\u001B[0m";
        public static final String ANSI_BLACK = "\u001B[30m";
        public static final String ANSI_RED = "\u001B[31m";
        public static final String ANSI_GREEN = "\u001B[32m";
        public static final String ANSI_YELLOW = "\u001B[33m";
        public static final String ANSI_BLUE = "\u001B[34m";
        public static final String ANSI_PURPLE = "\u001B[35m";
        public static final String ANSI_CYAN = "\u001B[36m";
        public static final String ANSI_WHITE = "\u001B[37m";
    }
}

