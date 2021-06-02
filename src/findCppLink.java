import cppLink.CppLink;
import util.JavaClass;
import util.loadJavaClass;

import java.util.List;

public class findCppLink {
    public static void main(String[] args){

        // an example
        String mainClassStrLast = "CameraManager$CameraManagerGlobal";
        String mainClassStr = "android.hardware.camera2." + mainClassStrLast;
        CppLink.run(mainClassStrLast, mainClassStr);


    }
}
