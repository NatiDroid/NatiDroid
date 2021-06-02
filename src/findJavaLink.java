import javaLink.JavaLink;

import java.util.ArrayList;

public class findJavaLink {
    public static void main(String[] args){

        // an example
        String mainClassStrLast = "SensorNotificationService";
        String mainClassStr = "com.android.server." + mainClassStrLast;
        ArrayList<String> starts_call = new ArrayList<String>();
        starts_call.add("onLocationChanged(");
        ArrayList<String> supportClassList = new ArrayList<String>();
        JavaLink.run(mainClassStrLast, mainClassStr, 1, starts_call, supportClassList);

    }
}
