using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.IO;
using System.Net;
using System.Collections.Specialized;

namespace Uploader
{
    class Program
    {
        private static String uploadURI = "http://wotapi.doot.ws/index.php";
        //private static String uploadURI = "http://localhost/index.php";

        private String replayDirectory = "";
        private FileSystemWatcher watcher;

        private string getRunningDirectory()
        {
            return System.IO.Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().GetName().CodeBase).Replace("file:\\", "");
        }
        private bool findReplayDirectory() {
            string exeDir = getRunningDirectory();
            exeDir += "\\replays\\";

            if (Directory.Exists(exeDir) && (File.GetAttributes(exeDir) & FileAttributes.Directory) == FileAttributes.Directory)
            {
                Console.WriteLine("Found replay directory: {0}", exeDir);
                setAndMonitorReplayDirectory(exeDir);
                return true; 
            }
            return false;
            
        }
        private bool initWatcher()
        {
            if (replayDirectory.Trim().Length == 0) { return false; }

            if (!Directory.Exists(replayDirectory) || FileAttributes.Directory != (File.GetAttributes(replayDirectory) & FileAttributes.Directory)) { return false; }

            watcher = new FileSystemWatcher();
            watcher.Filter = "*.wotreplay";
            watcher.Renamed += onReplayCompleted;
            watcher.Path = replayDirectory;
            watcher.EnableRaisingEvents = true;

            return true;
        }
        void onReplayCompleted(object sender, RenamedEventArgs e)
        {
            uploadReplay(e.FullPath);
        }

        private static bool HttpUploadFile(string url, string file, string paramName, string contentType, NameValueCollection nvc)
        {
            Console.WriteLine("Uploading {0} to {1}", file, url);
            string boundary = "---------------------------" + DateTime.Now.Ticks.ToString("x");
            byte[] boundarybytes = System.Text.Encoding.ASCII.GetBytes("\r\n--" + boundary + "\r\n");

            HttpWebRequest wr = (HttpWebRequest)WebRequest.Create(url);
            wr.ContentType = "multipart/form-data; boundary=" + boundary;
            wr.Method = "POST";
            wr.KeepAlive = true;
            wr.Credentials = System.Net.CredentialCache.DefaultCredentials;

            Stream rs = wr.GetRequestStream();

            string formdataTemplate = "Content-Disposition: form-data; name=\"{0}\"\r\n\r\n{1}";
            foreach (string key in nvc.Keys)
            {
                rs.Write(boundarybytes, 0, boundarybytes.Length);
                string formitem = string.Format(formdataTemplate, key, nvc[key]);
                byte[] formitembytes = System.Text.Encoding.UTF8.GetBytes(formitem);
                rs.Write(formitembytes, 0, formitembytes.Length);
            }
            rs.Write(boundarybytes, 0, boundarybytes.Length);

            string headerTemplate = "Content-Disposition: form-data; name=\"{0}\"; filename=\"{1}\"\r\nContent-Type: {2}\r\n\r\n";
            string header = string.Format(headerTemplate, paramName, file, contentType);
            byte[] headerbytes = System.Text.Encoding.UTF8.GetBytes(header);
            rs.Write(headerbytes, 0, headerbytes.Length);

            FileStream fileStream = new FileStream(file, FileMode.Open, FileAccess.Read);
            byte[] buffer = new byte[4096];
            int bytesRead = 0;
            while ((bytesRead = fileStream.Read(buffer, 0, buffer.Length)) != 0)
            {
                rs.Write(buffer, 0, bytesRead);
            }
            fileStream.Close();

            byte[] trailer = System.Text.Encoding.ASCII.GetBytes("\r\n--" + boundary + "--\r\n");
            rs.Write(trailer, 0, trailer.Length);
            rs.Close();

            WebResponse wresp = null;
            try
            {
                wresp = wr.GetResponse();
                Stream stream2 = wresp.GetResponseStream();
                StreamReader reader2 = new StreamReader(stream2);
                Console.WriteLine("File uploaded, server response is: {0}", reader2.ReadToEnd());
                return true;
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error uploading file:");
                Console.WriteLine(ex);
                if (wresp != null)
                {
                    wresp.Close();
                    wresp = null;
                }
                return false;
            }
            finally
            {
                wr = null;
            }
        }

        private bool processReplay(string file, out byte[] results)
        {
            byte[] ret = null;
            try
            {
                FileStream fs = File.OpenRead(file);
                BinaryReader br = new BinaryReader(fs);

                fs.Seek(4, SeekOrigin.Begin); // Skip magic number
                int blocks = br.ReadInt32();
                
                if (blocks == 3)
                {
                    Console.WriteLine("Loading chunks, {0} blocks found", blocks);

                    blocks = br.ReadInt32();
                    Console.WriteLine("Players chunk length {0}", blocks);
                    fs.Seek(blocks, SeekOrigin.Current);

                    blocks = br.ReadInt32();
                    Console.WriteLine("Frags chunk length {0}", blocks);
                    fs.Seek(blocks, SeekOrigin.Current);

                    blocks = br.ReadInt32();
                    Console.WriteLine("Details pickle length {0}", blocks);

                    int offset = (int)fs.Position;
                    fs.Seek(4, SeekOrigin.Begin);
                    ret = br.ReadBytes(offset);  // include the block count, too
                }
                else
                {
                    Console.WriteLine("Insufficient blocks");
                }

                br.Close();

                return true;
            }
            catch
            {
                return false;
            }
            finally
            {
                results = ret;
            }
        }

        private DateTime getLastUploadTime()
        {
            string tsFile = getRunningDirectory() + "\\last_upload.txt";
            try
            {
                DateTime t = DateTime.Parse(File.ReadAllText(tsFile));
                return t;
            }
            catch (Exception e)
            {
                return DateTime.MinValue;
            }
        }

        private void saveLastUploadTimestamp(DateTime ts)
        {
            string tsFile = getRunningDirectory() + "\\last_upload.txt";
            try
            {
                File.Delete(tsFile);
                StreamWriter f = File.CreateText(tsFile);
                f.Write(ts.ToString());
                f.Flush();
                f.Close();

            }
            catch (Exception e)
            {
                Console.WriteLine("Could not delete timestamp file");
            }
        }

        private void processReplayDirectory() {
            foreach(String f in Directory.GetFiles(replayDirectory, "*.wotreplay")) {
                DateTime lastUpload = getLastUploadTime();
                if (File.GetCreationTime(f) > lastUpload && f.StartsWith("temp") == false) {
                    uploadReplay(f);
                }
            }
            
        }

        public void setAndMonitorReplayDirectory(string s)
        {
            replayDirectory = s;
            if (!initWatcher())
            {
                Console.WriteLine("Could not initialize directory monitor.");
            }
            else
            {
                Console.WriteLine("Waiting for new replays to show up, hit ctrl+c to abort.");
                processReplayDirectory();
                while (true)
                {
                    watcher.WaitForChanged(WatcherChangeTypes.All);
                }
            }
        }

        private void uploadReplay(string file)
        {
            if (file.StartsWith("temp"))
                return;
            
            // We'll maybe use this later.
            NameValueCollection nvc = new NameValueCollection();
            try
            {
                
                if (HttpUploadFile(uploadURI, file, "file", "application/octet-stream", nvc))
                {
                    saveLastUploadTimestamp(File.GetCreationTime(file).AddSeconds(1));
                }
            }
            catch (System.Net.WebException ex)
            {
                Console.WriteLine("Couldn't upload {} - are you online?", file);
                //Console.WriteLine(ex.ToString());
            }
            catch (System.IO.IOException ex)
            {
                Console.WriteLine("Couldn't upload {} - is it in use?", file);
                //Console.WriteLine(ex.ToString());
            }
            
        }

        static void Main(string[] args)
        {
            Program p = new Program();
            if (args.Length > 1)
            {
                if (File.Exists(args[1]) && FileAttributes.Normal == (File.GetAttributes(args[1]) & FileAttributes.Normal))
                {
                    p.uploadReplay(args[1]);
                } else if (Directory.Exists(args[1]) && FileAttributes.Directory == (File.GetAttributes(args[1]) & FileAttributes.Directory))
                {
                    Console.WriteLine("Setting replay directory to {0}", args[1]);
                    p.setAndMonitorReplayDirectory(args[1]);
                }
            }
            else
            {
                if (p.findReplayDirectory() == false)
                {
                    Console.Write("No replays/directories to process");
                }
            }
        }
    }
}
