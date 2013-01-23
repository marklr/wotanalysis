using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.IO;
using System.Net;
using System.Collections.Specialized;
using System.Reflection;

namespace Uploader
{
    class Program
    {
        private static String uploadURI = "http://wotapi.doot.ws/index.php";
        private static String versionURI = "http://wotapi.doot.ws/version.txt";

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

        private static bool HttpUploadFile(string url, string file, string paramName, string contentType, NameValueCollection nvc, bool retry)
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
                string resp = reader2.ReadToEnd();

                if (resp.StartsWith("FAIL") && !retry)
                {
                    Console.WriteLine("Server didn't accept the upload, re-trying once.");
                    return HttpUploadFile(url, file, paramName, contentType, nvc, true);
                }
                Console.WriteLine("File uploaded, server response is: {0}", resp);
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

        private bool isReplayComplete(string file)
        {
            try
            {
                using(FileStream fs = File.OpenRead(file))
                {
                    using(BinaryReader br = new BinaryReader(fs))
                    {
                        fs.Seek(4, SeekOrigin.Begin); // Skip magic number
                        int blocks = br.ReadInt32();
                        return (blocks == 3);
                    }
                }
             } catch(Exception e) {
                 Console.WriteLine("Couldn't determine if replay is complete: ", e.Message);
                 return false;
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
                
                if (HttpUploadFile(uploadURI, file, "file", "application/octet-stream", nvc, false))
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

        private string checkForUpdate()
        {
            HttpWebRequest wr = null;
            WebResponse response = null;
            StreamReader sr = null;
            try
            {
                Version v = Assembly.GetExecutingAssembly().GetName().Version;
                wr  = (HttpWebRequest)WebRequest.Create(versionURI);
                response = (WebResponse)wr.GetResponse();
                using (Stream s = response.GetResponseStream())
                {
                    sr = new StreamReader(s);
                    Version nv = new Version(sr.ReadToEnd());
                    if (v.CompareTo(nv) < 0)
                    {
                        return nv.ToString(); // newer version detected.
                    }
                }
            }
            catch (Exception e)
            {
                Console.WriteLine("Couldn't check for a newer version");
                return null;
            }
            finally
            {
                response.Close();
                sr.Close();
            }

            return null;
        }

        static void Main(string[] args)
        {
            Program p = new Program();

            Console.WriteLine("[*] WOT Uploader v{0} starting up", Assembly.GetExecutingAssembly().GetName().Version.ToString());
            Console.WriteLine("[*] For more information, see http://wotmystats.blogspot.com");
            Console.WriteLine("[*] Checking for updates...");
            string newVersion = p.checkForUpdate();
            if (newVersion != null)
            {
                Console.WriteLine("[+] A newer version ({0}) is available, please see the website for more details", newVersion);
            }
            else
            {
                Console.WriteLine("[*] You're running the latest version, v{0}", Assembly.GetExecutingAssembly().GetName().Version.ToString());
            }
            Console.WriteLine("".PadRight(50, '-'));

            
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
