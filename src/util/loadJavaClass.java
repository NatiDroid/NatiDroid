package util;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import util.JavaClass;
import util.config;

import java.io.*;
import java.util.List;

public class loadJavaClass {


    public static List<JavaClass> load() {
        BufferedReader reader;
        try {
            reader = new BufferedReader(new FileReader(new File(config.javaClassFilePath)));
            JSONObject data = (JSONObject) JSON.parse(reader.readLine());
            reader.close();

            List<JavaClass> javaClasses = JSON.parseArray(data.getJSONArray("array").toJSONString(), JavaClass.class);


            return javaClasses;

        }catch (FileNotFoundException e) {
            e.printStackTrace();
        } catch (IOException e) {
            System.out.println("read data file error.\n" + e.getMessage());
			e.printStackTrace();
        } catch (Exception e) {
            System.out.println(e.getMessage());
			e.printStackTrace();
        }
        return null;
    }

}
