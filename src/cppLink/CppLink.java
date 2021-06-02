package cppLink;/////////////////////////////////////////////////////////////////////////////////////////////////
// Check ServiceManager.getService(BINDER_NAME) e.g.CAMERA_SERVICE_BINDER_NAME in JAVA
//
// Return a function called by the IBinder object. The actual implement is connected through BINDER_NAME in cpp
// 1. Find the incoming value of this function
// 2. Find the calling function of this function to return the object
/////////////////////////////////////////////////////////////////////////////////////////////////


import soot.*;
import soot.jimple.InvokeExpr;
import soot.jimple.StringConstant;
import soot.jimple.ThisRef;
import soot.jimple.internal.*;
import soot.jimple.spark.SparkTransformer;
import soot.jimple.toolkits.callgraph.CHATransformer;
import soot.jimple.toolkits.callgraph.CallGraph;
import soot.jimple.toolkits.callgraph.Edge;
import soot.jimple.toolkits.callgraph.Sources;
import soot.options.Options;
import util.LocalVar;
import util.config;
import util.helper;

import java.io.*;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;


public class CppLink extends SceneTransformer {

    static LinkedList<String> excludeList;

    static String mainClassStrLast = null;
    static String mainClassStr = null;

    static SootClass mainClass = null;
    static BufferedWriter out = null;

    public static void run(String mainClassStrLast, String mainClassStr){

        CppLink.mainClassStrLast = mainClassStrLast;
        CppLink.mainClassStr = mainClassStr;

        helper.createDir("cpplink");
        try{
            out = new BufferedWriter(new FileWriter("cpplink/cpp_link_"+ mainClassStr +".txt"));
        }catch (IOException e){
            e.printStackTrace();
            System.exit(1);
        }

        String classesDir = "AndroidSdk/sources/android-26";

        String javapath = "";
        String path = config.loadJarPath();
        System.out.println(path);
        Scene.v().setSootClassPath(path);

        CppLink analysis = new CppLink();
        Pack pack = PackManager.v().getPack("wjtp");


        pack.add(new Transform("wjtp.CppLink", analysis));


        excludeJDKLibrary();

        Options.v().set_whole_program(true);
        Options.v().set_app(true);
        Options.v().set_validate(true);

        SootClass c = Scene.v().forceResolve(mainClassStr, SootClass.BODIES);

        c.setApplicationClass();

        Scene.v().loadNecessaryClasses();

        //Set all entrypoints and find the mainclass
        List<SootMethod> entryPoints = new ArrayList<SootMethod>();
        for(SootClass sc : Scene.v().getApplicationClasses()) {
            if(!sc.getName().contains("jdk.")){
                //Output all loaded class names

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

        System.out.println("close the out stream." + PrintColor.ANSI_RESET);

        try{
            out.close();
        }catch (IOException e){
            e.printStackTrace();
            System.exit(1);
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

    public boolean isBinderMethod(SootMethod m){
        //Get the class of the method
        SootClass c = m.getDeclaringClass();
        SootClass targetClass = null;
        //The actual implement class
        for (SootClass temC : Scene.v().getApplicationClasses()) {
            if(temC.getName().equals(c.getName() + "$Stub$Proxy")){
                System.out.println(temC.getName());
                targetClass = temC;
                break;
            }
        }
        if(targetClass==null){
            throw new IllegalArgumentException("Cannot find implement class: " + c.getName() + "$Stub$Proxy");
        }

        //Find the method impl in the implement class
        SootMethod implMethod = null;
        for(SootMethod method : targetClass.getMethods()) {
            if(method.getSubSignature().equals(m.getSubSignature())){
                implMethod = method;
                break;
            }
        }
        if(implMethod==null){
            throw new IllegalArgumentException("Cannot find implement method: " + m.getSignature());
        }

        //Get the code of the actual impl method
        Body body = implMethod.getActiveBody();

        //Contains the behavior of sending Parcel, it is the IBinder function, which needs to be connected to C++
        for(Unit u: body.getUnits()) {
            String unitString = u.toString();
            if(unitString.contains("<android.os.Parcel: android.os.Parcel obtain()>()")){
                int i=0;
                return true;
            }
        }

        return false;
    }


    protected void pre_visit(SootMethod m, SootMethod p, CallGraph callGraph, CallGraph bigCallGraph, List<String> permissionStrs, List<String> visitedMethodSig, int depth, LocalVar globalVar) throws IOException {


        if(!visitedMethodSig.contains(m.getSignature())) {
            visitedMethodSig.add(m.getSignature());
        }else{
            return;
        }

        //AIDL
        if(m.getSignature().contains("$Stub: boolean onTransact(")){
            //stub -> interface, interface -> Proxy
            SootClass classProxy = getInnerClass(m.getDeclaringClass(),"Proxy");
            SootMethod mthodInterface = classProxy.getMethod(p.getName(),p.getParameterTypes());
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

        }else if (m.getSignature().contains("void run(")) {
            return;

        }else if (m.getSignature().contains("createFromParcel(")) {
            // <android.bluetooth.BluetoothDevice$2: java.lang.Object createFromParcel(android.os.Parcel)>
            return;
        }


        if(m.getDeclaringClass().isAbstract() || m.getDeclaringClass().isInterface())
        {
            System.out.println(PrintColor.ANSI_RED + m + "isAbstract "+ m.getDeclaringClass().isAbstract() + ";isInterface "+ m.getDeclaringClass().isInterface() + PrintColor.ANSI_RESET);
            return;
        }

        //Finding all the methods whose function input contains the object theoretically requires permissions
        if (m.getSignature().contains("void <init>")) {
            //Traverse to find the parameter type of the init class
            String findClass = m.getDeclaringClass().getName();
            for(SootClass sc : Scene.v().getApplicationClasses()) {
                if (!sc.getName().contains("jdk.")&& !sc.isAbstract() && !sc.isInterface()) {
                    for(SootMethod temm : sc.getMethods()) {
                        List<Type> types= temm.getParameterTypes();
                        for(Type typeTem : types) {
                            if(typeTem.toString().equals(findClass)){
                                depth++;
                                pre_visit(temm, m, callGraph, bigCallGraph, permissionStrs, visitedMethodSig, depth, globalVar);
                                break;
                            }
                        }
                    }
                }
            }
        }


        //Perform normal CFG analysis
        Iterator<Edge> temEdgesIterator = callGraph.edgesInto(m);
        Iterator<MethodOrMethodContext> parents = new Sources(temEdgesIterator);


        if (parents == null) {
            return;
        }

        while (parents.hasNext()) {
            SootMethod parent = (SootMethod) parents.next();

            System.out.println(PrintColor.ANSI_RESET + m + PrintColor.ANSI_GREEN + " <=== " + parent + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);
            /*
            * If there are global variables, if you want to find out whether the function called by all global variables is a c function, then record
            * */
            if(globalVar !=null){
                System.out.println("************");
                System.out.println("FIND globalVar call FUNCTION" + parent);
                System.out.println("************");
                Body body = parent.getActiveBody();
                List<LocalVar> localVars = new ArrayList<LocalVar>();
                String mXxxService = null;
                for(Unit u: body.getUnits()) {

                    if(u instanceof JIdentityStmt) {

                        //Global variable reference (class variable)
                        JimpleLocal left = (JimpleLocal)((JIdentityStmt) u).getLeftOp();
                        String left_local_name = left.getName();

                        Value ref = ((JIdentityStmt) u).getRightOp();
                        localVars.add(new LocalVar(left_local_name, ref));
                    }else if(u instanceof JAssignStmt) {
                        Value right_warp = ((JAssignStmt) u).getRightOpBox().getValue();
                        Value left_warp = ((JAssignStmt) u).getLeftOpBox().getValue();

                        //Two cases on the right
                        if(right_warp instanceof JVirtualInvokeExpr) {
                            JVirtualInvokeExpr right = (JVirtualInvokeExpr) right_warp;
                            Value right_base = right.getBase();
                            JimpleLocal right_local = (JimpleLocal) right_base;

                            String right_localName = right_local.getName();
                            SootMethod right_method = right.getMethod();
                            String right_fun = right_method.getSignature();

                            JimpleLocal left = (JimpleLocal) left_warp;
                            String left_localName = left.getName();

                            if (mXxxService != null && right_localName.equals(mXxxService)) {
                                if(isBinderMethod(right_method)){
                                    System.out.println(PrintColor.ANSI_BLUE + right_method + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);
                                    out.write(right_method.toString()+ "|" + permissionStrs+"\n");
                                }
                            }
                        }
                        else if(right_warp instanceof JInterfaceInvokeExpr) {
                            JInterfaceInvokeExpr right = (JInterfaceInvokeExpr) right_warp;
                            Value right_base = right.getBase();
                            JimpleLocal right_local = (JimpleLocal) right_base;

                            String right_localName = right_local.getName();
                            SootMethod right_method = right.getMethod();
                            String right_fun = right_method.getSignature();

                            JimpleLocal left = (JimpleLocal) left_warp;
                            String left_localName = left.getName();


                            if (mXxxService != null && right_localName.equals(mXxxService)) {
                                if(isBinderMethod(right_method)){
                                    System.out.println(PrintColor.ANSI_BLUE + right_method + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);
                                    out.write(right_method.toString()+ "|" + permissionStrs+"\n");
                                }
                            }

                        }
                        else if(right_warp instanceof JStaticInvokeExpr) {
                            JStaticInvokeExpr right = (JStaticInvokeExpr) right_warp;

                            SootMethod right_method = right.getMethod();
                            String right_fun = right_method.getSignature();

                            JimpleLocal left = (JimpleLocal) left_warp;
                            String left_localName = left.getName();

                        }
                        else if(left_warp instanceof JimpleLocal && right_warp instanceof JInstanceFieldRef) {
                            // Global variable assignment
                            // Local.xxx = Local;
                            // $r3 = r0.<android.net.sip.SipManager: android.net.sip.ISipService mSipService>

                            //r0.<android.net.sip.SipManager: android.net.sip.ISipService mSipService>
                            JInstanceFieldRef right = (JInstanceFieldRef) right_warp;

                            //r0
                            JimpleLocal right_local = (JimpleLocal) right.getBase();
                            String right_localName = right_local.getName();

                            //<android.net.sip.SipManager: android.net.sip.ISipService mSipService>
                            SootField right_field = right.getField();

                            JimpleLocal left = (JimpleLocal) left_warp;
                            String left_localName = left.getName();

                            String new_right = "";
                            for(LocalVar localVar: localVars){
                                if(right_localName.equals(localVar.left)){
                                    new_right = localVar.right.toString();
                                }
                            }

                            if(globalVar.left.equals(new_right+"."+right_field.toString())){
                                mXxxService = left_localName;
                            }
                        }
                    }else if(u instanceof JInvokeStmt){
                        Value value = ((JInvokeStmt) u).getInvokeExprBox().getValue();
                        if(value instanceof JInterfaceInvokeExpr) {
                            JInterfaceInvokeExpr interfaceValue = (JInterfaceInvokeExpr) value;
                            SootMethod mathod = interfaceValue.getMethod();
                            String localName = ((JimpleLocal) interfaceValue.getBase()).getName();

                            if (mXxxService != null && localName.equals(mXxxService)) {
                                if(isBinderMethod(mathod)){
                                    System.out.println(PrintColor.ANSI_BLUE + mathod + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);
                                    out.write(mathod.toString()+ "|" + permissionStrs+"\n");
                                }
                            }

                        }
                    }
                }

            }

            /*
             * If there is getService() in the function
             * Find asInterface at the same level
             * 1. Global variables assigned to
             * 2. The name of the c function called
             * */
            if(depth==0){
                System.out.println("************");
                System.out.println("FIND asInterface() FUNCTION WHICH CONTAINS IxxxService getXXXService()" + m);
                System.out.println("************");
                Body body = m.getActiveBody();

                List<LocalVar> localVars = new ArrayList<LocalVar>();
                for(Unit u: body.getUnits()) {
                    //assignment xxx = xxx;

                    if(u instanceof JAssignStmt) {
                        Value right_warp = ((JAssignStmt) u).getRightOpBox().getValue();
                        //two cases on the right
                        if(right_warp instanceof JVirtualInvokeExpr) {
                            JVirtualInvokeExpr right = (JVirtualInvokeExpr) right_warp;
                            Value right_base = right.getBase();
                            JimpleLocal right_local = (JimpleLocal) right_base;

                            String right_localName = right_local.getName();
                            SootMethod right_method = right.getMethod();
                            String right_fun = right_method.getSignature();

                            Value left_warp = ((JAssignStmt) u).getLeftOpBox().getValue();
                            JimpleLocal left = (JimpleLocal) left_warp;
                            String left_localName = left.getName();
                            // Find the variable returned by method m and output all isBinder(interface) functions called by m
                            for(LocalVar localVar: localVars){

                                if(localVar.right instanceof SootMethod && right_localName.equals(localVar.left)){
                                    if(isBinderMethod(right_method)){
                                        System.out.println(PrintColor.ANSI_BLUE + right_method + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);
                                        out.write(right_method.toString()+ "|" + permissionStrs+"\n");
                                    }
                                }
                            }

                            if (right_fun.contains("asInterface(")) {
                                localVars.add(new LocalVar(left_localName, right_method));
                            }
                        }
                        else if(right_warp instanceof JInterfaceInvokeExpr) {
                            JInterfaceInvokeExpr right = (JInterfaceInvokeExpr) right_warp;
                            Value right_base = right.getBase();
                            JimpleLocal right_local = (JimpleLocal) right_base;

                            String right_localName = right_local.getName();
                            SootMethod right_method = right.getMethod();
                            String right_fun = right_method.getSignature();

                            Value left_warp = ((JAssignStmt) u).getLeftOpBox().getValue();
                            JimpleLocal left = (JimpleLocal) left_warp;
                            String left_localName = left.getName();

                            for(LocalVar localVar: localVars){

                                if(localVar.right instanceof SootMethod && right_localName.equals(localVar.left)){
                                    if(isBinderMethod(right_method)){
                                        System.out.println(PrintColor.ANSI_BLUE + right_method + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);
                                        out.write(right_method.toString()+ "|" + permissionStrs+"\n");
                                    }
                                }
                            }

                            if (right_fun.contains("asInterface(")) {
                                localVars.add(new LocalVar(left_localName, right_method));
                            }

                        }
                        else if(right_warp instanceof JStaticInvokeExpr) {
                            JStaticInvokeExpr right = (JStaticInvokeExpr) right_warp;

                            SootMethod right_method = right.getMethod();
                            String right_fun = right_method.getSignature();

                            Value left_warp = ((JAssignStmt) u).getLeftOpBox().getValue();
                            JimpleLocal left = (JimpleLocal) left_warp;
                            String left_localName = left.getName();
                            // Find the variable returned by method m and output all isBinder(interface) functions called by m
                            if (right_fun.contains("asInterface(")) {
                                localVars.add(new LocalVar(left_localName, right_method));
                            }
                        }
                        else if(right_warp instanceof JimpleLocal) {
                            // xxx = Local;
                            JimpleLocal right = (JimpleLocal) right_warp;
                            String right_localName = right.getName();

                            Value left_warp = ((JAssignStmt) u).getLeftOpBox().getValue();
                            if(left_warp instanceof JimpleLocal){
                                // Local = Local;
                                JimpleLocal left = (JimpleLocal) left_warp;
                                String left_localName = left.getName();
                                for(LocalVar localVar: localVars){
                                    if(right_localName.equals(localVar.left)){
                                        localVar.left = left_localName;
                                    }
                                }
                            }
                            else if(left_warp instanceof JInstanceFieldRef){
                                // Global variable assignment
                                // Local.xxx = Local;
                                //r0.<android.net.sip.SipManager: android.net.sip.ISipService mSipService> = $r3

                                //r0.<android.net.sip.SipManager: android.net.sip.ISipService mSipService>
                                JInstanceFieldRef left = (JInstanceFieldRef) left_warp;

                                //r0
                                JimpleLocal left_local = (JimpleLocal)left.getBase();
                                String left_localName = left_local.getName();

                                //<android.net.sip.SipManager: android.net.sip.ISipService mSipService>
                                SootField left_field = left.getField();

                                String new_left = "";
                                for(LocalVar localVar: localVars){
                                    if(left_localName.equals(localVar.left)){
                                        new_left = localVar.right.toString();
                                    }
                                }

                                for(LocalVar localVar: localVars){
                                    if(right_localName.equals(localVar.left)){
                                        localVar.left = new_left + "." + left_field.toString();
                                        globalVar = localVar;
                                    }
                                }
                            }



                        }

                    }else if(u instanceof JIdentityStmt) {
                        //Global variable reference (class variable)
                        JimpleLocal left = (JimpleLocal)((JIdentityStmt) u).getLeftOp();
                        String left_local_name = left.getName();

                        Value ref = ((JIdentityStmt) u).getRightOp();
                        localVars.add(new LocalVar(left_local_name, ref));
                    }
                }

                for(LocalVar localVar: localVars){
                    System.out.println(localVar.left + " === " + localVar.right);
                }
            }


            // If a function return value is IxxService
            String return_class = m.getReturnType().toString();
            // android.hardware.ICameraService
            // Search in the string according to the specified pattern
            String pattern = "\\.I\\S.+?Service";
            Pattern r = Pattern.compile(pattern);
            Matcher re_result = r.matcher(return_class);

            if(re_result.find()){
                // getCameraService
                System.out.println("************");
                System.out.println("SEARCH FROM FUNCTION WHICH CONTAINS IxxxService getXXXService()" + parent);
                System.out.println("************");
                Body body = parent.getActiveBody();

                List<SootMethod> methodList = new ArrayList<SootMethod>();
                String last_local = null;

                for(Unit u: body.getUnits()) {
                    //siign xxx = xxx;
                    boolean aaa = u instanceof JAssignStmt;
                    boolean bbb = u instanceof JInvokeStmt;
                    if(u instanceof JAssignStmt) {
                        Value right_warp = ((JAssignStmt) u).getRightOpBox().getValue();

                        // two cases on thright
                        if(right_warp instanceof JVirtualInvokeExpr) {
                            JVirtualInvokeExpr right = (JVirtualInvokeExpr) right_warp;
                            Value right_base = right.getBase();
                            JimpleLocal right_local = (JimpleLocal) right_base;

                            String right_localName = right_local.getName();
                            SootMethod right_method = right.getMethod();
                            String right_fun = right_method.getSignature();

                            Value left_warp = ((JAssignStmt) u).getLeftOpBox().getValue();
                            JimpleLocal left = (JimpleLocal) left_warp;
                            String left_localName = left.getName();

                            // Find the variable returned by method m and output all isBinder(interface) functions called by m
                            if (last_local != null && right_localName.equals(last_local)) {
                                if(isBinderMethod(right_method)){
                                    methodList.add(right_method);
                                    System.out.println(PrintColor.ANSI_BLUE + right_method + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);
                                    out.write(right_method.toString()+ "|" + permissionStrs+"\n");
                                }

                            }else if (right_fun.contains(m.getSignature())) {
                                last_local = left_localName;

                            }
                        }else if(right_warp instanceof JInterfaceInvokeExpr) {
                            JInterfaceInvokeExpr right = (JInterfaceInvokeExpr) right_warp;
                            Value right_base = right.getBase();
                            JimpleLocal right_local = (JimpleLocal) right_base;

                            String right_localName = right_local.getName();
                            SootMethod right_method = right.getMethod();
                            String right_fun = right_method.getSignature();

                            Value left_warp = ((JAssignStmt) u).getLeftOpBox().getValue();
                            JimpleLocal left = (JimpleLocal) left_warp;
                            String left_localName = left.getName();

                            if (last_local != null && right_localName.equals(last_local)) {
                                if(isBinderMethod(right_method)){
                                    methodList.add(right_method);
                                    System.out.println(PrintColor.ANSI_BLUE + right_method + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);
                                    out.write(right_method.toString()+ "|" + permissionStrs+"\n");
                                }
                            }else if (right_fun.contains(m.getSignature())) {
                                last_local = left_localName;

                            }
                        }else if(right_warp instanceof JimpleLocal) {

                        }
                        int iii=0;
                    }else if(u instanceof JInvokeStmt){
                        Value value = ((JInvokeStmt) u).getInvokeExprBox().getValue();
                        if(value instanceof JInterfaceInvokeExpr) {
                            JInterfaceInvokeExpr interfaceValue = (JInterfaceInvokeExpr) value;
                            SootMethod mathod = interfaceValue.getMethod();
                            String localName = ((JimpleLocal) interfaceValue.getBase()).getName();

                            if (last_local != null && localName.equals(last_local)) {
                                if(isBinderMethod(mathod)){
                                    methodList.add(mathod);
                                    System.out.println(PrintColor.ANSI_BLUE + mathod + PrintColor.ANSI_YELLOW + "  :::  " + permissionStrs);
                                    out.write(mathod.toString()+ "|" + permissionStrs+"\n");
                                }
                            }

                        }
                    }
                    int iii=0;


                }
                int iii=0;


            }

            depth++;
            pre_visit(parent, m, callGraph, bigCallGraph, permissionStrs, visitedMethodSig, depth, globalVar);


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

    // Find a method for permission detection and store the requested permission
    public List<String> methodHasCheckPermission(SootMethod m){
        List<String> permissionStrs = new ArrayList<String>();
        // The native method does not check
        if(m.isNative()){
            return permissionStrs;
        }
        if(m.toString().contains("createSipService(")){
            int iii=0;
        }
        Body fun = m.getActiveBody();
        // Traverse the code block where the function is located
        for(Unit u: fun.getUnits()) {
            String unitStrTem = u.toString();
            if(unitStrTem.contains("getService(")){
                if(u instanceof JAssignStmt) {
                    Value v = ((JAssignStmt) u).getRightOpBox().getValue();
                    for (ValueBox vvv : v.getUseBoxes()) {
                        if (vvv.getValue() instanceof StringConstant) {
                            //check permission
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
                    System.err.println("methodHasCheckPermission: Unknown JxxStmt type");
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

        if (mainClassMethodList.size()==0){
            System.out.println(mainClassStr + "DOES NOT EXIST");
        }
        for(SootMethod m : mainClassMethodList) {
            System.out.println(m);
        }

        for(SootMethod m : mainClassMethodList) {

            List<String> permissionStrs = methodHasCheckPermission(m);
            if(permissionStrs.size()!=0){
                System.out.println(m +"  "+ permissionStrs);
                // Find the asInterface() in the m function
                PermissionMthod permissionMthod = new PermissionMthod(m, permissionStrs);
                serviceHasPermissionMethods.put(m.getSignature(), permissionMthod);
            }
        }
        System.out.println("\n\n\n\n");
        
        for(PermissionMthod permissionMthod : serviceHasPermissionMethods.values()){
            SootMethod m = permissionMthod.parentMethod;
            List<String> visitedMethodSig = new ArrayList<String>();
            System.out.println("#########################");
            System.out.println("SEARCH FROM FUNCTION WHICH CONTAINS getService()" + m + permissionMthod.permissionStrs);
            System.out.println("#########################");
            int depth = 0;
            try {
                pre_visit(m, null, callGraph, bigCallGraph, permissionMthod.permissionStrs, visitedMethodSig, depth, null);
            } catch (IOException e) {
                e.printStackTrace();
            }
        }




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

