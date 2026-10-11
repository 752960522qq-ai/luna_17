package com.hatch.loader;

import java.io.IOException;
import java.util.*;

/** Deterministic dependency order with exact version matching and cycle checks. */
final class DependencyOrder {
    static final class Node {
        final String id, version;
        final Map<String,String> requires;
        Node(String id, String version, Map<String,String> requires) {
            this.id=id; this.version=version; this.requires=requires;
        }
    }
    static List<String> resolve(Collection<Node> nodes) throws IOException {
        Map<String,Node> all=new TreeMap<>();
        for(Node node:nodes) if(all.put(node.id,node)!=null) throw new IOException("重复模组 ID: "+node.id);
        List<String> order=new ArrayList<>(); Map<String,Integer> marks=new HashMap<>();
        for(String id:all.keySet()) visit(id,all,marks,order);
        return order;
    }
    private static void visit(String id,Map<String,Node> all,Map<String,Integer> marks,List<String> order) throws IOException {
        int mark=marks.containsKey(id)?marks.get(id):0;
        if(mark==2)return;
        if(mark==1)throw new IOException("循环依赖: "+id);
        Node node=all.get(id); marks.put(id,1);
        for(String required:new TreeSet<>(node.requires.keySet())) {
            Node dependency=all.get(required);
            if(dependency==null)throw new IOException(id+" 缺少依赖: "+required);
            if(!dependency.version.equals(node.requires.get(required)))throw new IOException(id+" 依赖版本不兼容: "+required);
            visit(required,all,marks,order);
        }
        marks.put(id,2);order.add(id);
    }
}
