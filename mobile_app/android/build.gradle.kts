allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

fun configureAndroidCompileOptions(androidExtension: Any) {
    val compileOptions =
        androidExtension.javaClass.methods
            .firstOrNull { it.name == "getCompileOptions" && it.parameterCount == 0 }
            ?.invoke(androidExtension)
            ?: return

    compileOptions.javaClass
        .getMethod("setSourceCompatibility", JavaVersion::class.java)
        .invoke(compileOptions, JavaVersion.VERSION_17)
    compileOptions.javaClass
        .getMethod("setTargetCompatibility", JavaVersion::class.java)
        .invoke(compileOptions, JavaVersion.VERSION_17)
}

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)

    plugins.withId("com.android.application") {
        extensions.findByName("android")?.let(::configureAndroidCompileOptions)
    }

    plugins.withId("com.android.library") {
        extensions.findByName("android")?.let(::configureAndroidCompileOptions)
    }

    tasks.withType<JavaCompile>().configureEach {
        sourceCompatibility = JavaVersion.VERSION_17.toString()
        targetCompatibility = JavaVersion.VERSION_17.toString()
        options.release.set(17)
    }

    tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
