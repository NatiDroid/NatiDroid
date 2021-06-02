package util;

import java.io.File;

public class helper {
    public static boolean createDir(String destDirName) {
        File dir = new File(destDirName);
        if (dir.exists()) {

            return true;
        }
        if (!destDirName.endsWith(File.separator)) {
            destDirName = destDirName + File.separator;
        }

        if (dir.mkdirs()) {
            System.out.println("creat dir" + destDirName + "successfully！");
            return true;
        } else {
            System.out.println("creat dir" + destDirName + "fail！");
            return false;
        }
    }
}
