class PatternRenamer < Formula
  desc "Simple GUI file renamer using regexes built with Python, GTK and LibAdwaita"
  homepage "https://github.com/GeoffreyCoulaud/gui-renamer"
  head "https://github.com/GeoffreyCoulaud/gui-renamer.git", branch: "main"

  depends_on "gettext" => :build
  depends_on "meson" => :build
  depends_on "ninja" => :build
  depends_on "pkg-config" => :build
  depends_on "desktop-file-utils"
  depends_on "gtk4"
  depends_on "libadwaita"
  depends_on "pygobject3"
  depends_on "python@3.14"

  def install
    python3 = "python3.14"
    venv_dir = libexec/"venv"

    # Create a virtual environment
    system python3, "-m", "venv", venv_dir

    # Install Python dependencies in the virtual environment
    system venv_dir/"bin/pip", "install", "--upgrade", "pip", "setuptools"

    # Install all required Python dependencies
    system venv_dir/"bin/pip", "install", "pygobject", "pathvalidate>=3.3.1"

    # Set environment variables for meson to use our Python
    ENV["PYTHON"] = venv_dir/"bin/python"

    # Configure with meson
    system "meson", "setup", "build",
      "--prefix=#{prefix}",
      "--buildtype=release",
      "-Dprofile=release"

    # Build and install
    system "meson", "compile", "-C", "build"
    system "meson", "install", "-C", "build"

    # Rename the original executable first
    mv bin/"pattern-renamer", bin/"pattern-renamer-real"

    # Create a wrapper script that activates the venv
    (bin/"pattern-renamer").write <<~EOS
      #!/bin/bash
      export PYTHONPATH="#{venv_dir}/lib/python3.14/site-packages:$PYTHONPATH"
      exec "#{venv_dir}/bin/python" "#{bin}/pattern-renamer-real" "$@"
    EOS

    chmod 0755, bin/"pattern-renamer"
  end

  def post_install
    system "#{Formula["glib"].opt_bin}/glib-compile-schemas", "#{HOMEBREW_PREFIX}/share/glib-2.0/schemas"
    system "#{Formula["gtk4"].opt_bin}/gtk4-update-icon-cache", "-f", "-t", "#{HOMEBREW_PREFIX}/share/icons/hicolor"
  end

  test do
    # Test that the Python environment is correctly set up
    assert_predicate bin/"pattern-renamer", :exist?
    assert_predicate bin/"pattern-renamer", :executable?
    
    # Test that required Python modules can be imported in the venv
    system libexec/"venv/bin/python", "-c", <<~EOS
      import pathvalidate
      import gi
      gi.require_version('Gtk', '4.0')
      gi.require_version('Adw', '1')
      from gi.repository import Gtk, Adw
      print("All dependencies imported successfully")
    EOS
  end
end
