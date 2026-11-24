using System;
using Rhino.Geometry;
public static class PalaceBuffers {
    public static Mesh MeshFromBuffers(byte[] coordinates, byte[] indices) {
        float[] v = new float[coordinates.Length / 4];
        int[] t = new int[indices.Length / 4];
        Buffer.BlockCopy(coordinates, 0, v, 0, coordinates.Length);
        Buffer.BlockCopy(indices, 0, t, 0, indices.Length);
        Mesh mesh = new Mesh();
        for (int i = 0; i < v.Length; i += 3) mesh.Vertices.Add(v[i], v[i+1], v[i+2]);
        for (int i = 0; i < t.Length; i += 3) mesh.Faces.AddFace(t[i], t[i+1], t[i+2]);
        mesh.Normals.ComputeNormals();
        mesh.Compact();
        return mesh;
    }
}
